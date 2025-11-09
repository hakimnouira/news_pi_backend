#news_scraper.py
import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import feedparser
from bs4 import BeautifulSoup
import hashlib
from urllib.parse import urljoin, urlparse
import time
from PIL import Image
from io import BytesIO

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NewsScraperBot:
    """Bot de scraping d'articles avec extraction d'images HD"""
    
    def __init__(self, newsapi_key: Optional[str] = None):
        self.newsapi_key = newsapi_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Sources RSS populaires
        self.rss_feeds = [
            "http://rss.cnn.com/rss/cnn_topstories.rss",
            "http://feeds.bbci.co.uk/news/rss.xml",
            "https://www.theguardian.com/world/rss",
            "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
            "https://feeds.reuters.com/reuters/topNews",
        ]
    
    def scrape_from_rss(self, max_articles: int = 10) -> List[Dict]:
        """Scrape articles depuis flux RSS"""
        articles = []
        
        logger.info(f"Scraping {len(self.rss_feeds)} RSS feeds...")
        
        for feed_url in self.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                source_name = feed.feed.get('title', 'Unknown Source')
                
                for entry in feed.entries[:max_articles]:
                    try:
                        article = self._parse_rss_entry(entry, source_name)
                        if article:
                            articles.append(article)
                            
                    except Exception as e:
                        logger.warning(f"Error parsing RSS entry: {e}")
                        continue
                
                logger.info(f"✓ Scraped {len(articles)} from {source_name}")
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Failed to fetch RSS feed {feed_url}: {e}")
                continue
        
        return articles[:max_articles]
    
    def _parse_rss_entry(self, entry, source_name: str) -> Optional[Dict]:
        """Parse une entrée RSS"""
        try:
            # Texte de l'article
            content = entry.get('summary', entry.get('description', ''))
            if not content or len(content.split()) < 50:
                return None
            
            # Nettoyage HTML
            soup = BeautifulSoup(content, 'html.parser')
            clean_text = soup.get_text(separator=' ', strip=True)
            
            # ✅ EXTRACTION IMAGE HD AMÉLIORÉE
            image_url = self._extract_best_image_from_entry(entry, entry.get('link', ''))
            
            # ✅ DATE DE PUBLICATION CORRIGÉE
            pub_date = "Not specified"
            try:
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    date_obj = datetime(*entry.published_parsed[:6])
                    pub_date = date_obj.strftime("%B %d, %Y")
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    date_obj = datetime(*entry.updated_parsed[:6])
                    pub_date = date_obj.strftime("%B %d, %Y")
                elif entry.get('published'):
                    # Essayer de parser la date string
                    from dateutil import parser as date_parser
                    date_obj = date_parser.parse(entry.get('published'))
                    pub_date = date_obj.strftime("%B %d, %Y")
                elif entry.get('updated'):
                    from dateutil import parser as date_parser
                    date_obj = date_parser.parse(entry.get('updated'))
                    pub_date = date_obj.strftime("%B %d, %Y")
            except Exception as e:
                logger.warning(f"Failed to parse date: {e}")
                pub_date = datetime.now().strftime("%B %d, %Y")
            
            # ✅ ESSAYER DE RÉCUPÉRER LE TEXTE COMPLET
            article_url = entry.get('link', '')
            full_text = clean_text
            
            # Si le texte est court, essayer de scraper l'article complet
            if len(clean_text.split()) < 200 and article_url:
                logger.info(f"Text too short ({len(clean_text.split())} words), scraping full article...")
                scraped_text = self.scrape_article_full_text(article_url)
                if scraped_text and len(scraped_text.split()) > len(clean_text.split()):
                    full_text = scraped_text
                    logger.info(f"✓ Full text scraped: {len(full_text.split())} words")
            
            article = {
                "title": entry.get('title', 'No Title'),
                "text": full_text,
                "url": article_url,
                "source": source_name,
                "published_date": pub_date,
                "image_url": image_url,
                "scraped_at": datetime.now().isoformat()
            }
            
            return article
            
        except Exception as e:
            logger.error(f"Error parsing RSS entry: {e}")
            return None
    
    def _extract_best_image_from_entry(self, entry, article_url: str = None) -> Optional[str]:
        """
        ✅ EXTRACTION IMAGE HD OPTIMISÉE
        Essaye plusieurs méthodes pour trouver la meilleure image
        """
        best_image = None
        best_resolution = 0
        
        # 🔍 MÉTHODE 1: media:content (standard RSS)
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                img_url = media.get('url')
                width = int(media.get('width', 0))
                height = int(media.get('height', 0))
                resolution = width * height
                
                if resolution > best_resolution:
                    best_image = img_url
                    best_resolution = resolution
        
        # 🔍 MÉTHODE 2: media:thumbnail (souvent meilleure qualité)
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            for thumb in entry.media_thumbnail:
                img_url = thumb.get('url')
                # Modifier l'URL pour obtenir la version HD
                img_url = self._get_hd_version(img_url)
                width = int(thumb.get('width', 0))
                height = int(thumb.get('height', 0))
                resolution = width * height
                
                if resolution > best_resolution:
                    best_image = img_url
                    best_resolution = resolution
        
        # 🔍 MÉTHODE 3: enclosure
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if 'image' in enc.get('type', ''):
                    img_url = enc.get('href')
                    img_url = self._get_hd_version(img_url)
                    if img_url:
                        best_image = img_url
        
        # 🔍 MÉTHODE 4: Parser le HTML du contenu
        if not best_image or best_resolution < 100000:  # < 316x316
            content = entry.get('summary', entry.get('description', ''))
            soup = BeautifulSoup(content, 'html.parser')
            
            # Chercher toutes les images
            images = soup.find_all('img')
            for img in images:
                img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
                if img_url:
                    img_url = self._get_hd_version(img_url)
                    width = int(img.get('width', 0)) if img.get('width', '').isdigit() else 0
                    height = int(img.get('height', 0)) if img.get('height', '').isdigit() else 0
                    resolution = width * height
                    
                    if resolution > best_resolution:
                        best_image = img_url
                        best_resolution = resolution
        
        # 🔍 MÉTHODE 5: Scraper la page complète pour trouver l'image principale
        if not best_image and article_url:
            logger.info(f"Trying to scrape image from article page: {article_url}")
            scraped_img = self._scrape_main_image_from_page(article_url)
            if scraped_img:
                best_image = scraped_img
        
        # ✅ Valider et retourner
        if best_image:
            # Assurer que l'URL est absolue
            if best_image.startswith('//'):
                best_image = 'https:' + best_image
            elif best_image.startswith('/'):
                if article_url:
                    best_image = urljoin(article_url, best_image)
            
            logger.info(f"✓ Found image: {best_image[:80]}... (resolution: {best_resolution})")
            return best_image
        
        return None
    
    def _get_hd_version(self, img_url: str) -> str:
        """
        ✅ TRANSFORME UNE URL D'IMAGE EN VERSION HD
        Remplace les paramètres de taille pour obtenir la meilleure qualité
        """
        if not img_url:
            return img_url
        
        # Patterns courants de redimensionnement d'images
        replacements = [
            # Guardian
            ('width=140', 'width=1200'),
            ('width=300', 'width=1200'),
            ('width=460', 'width=1200'),
            # NYT
            ('quality=75', 'quality=100'),
            ('width=200', 'width=2000'),
            ('width=600', 'width=2000'),
            # General
            ('-small', '-large'),
            ('-thumb', '-full'),
            ('-medium', '-large'),
            ('_s.jpg', '_b.jpg'),
            ('_m.jpg', '_b.jpg'),
        ]
        
        hd_url = img_url
        for old, new in replacements:
            hd_url = hd_url.replace(old, new)
        
        return hd_url
    
    def _scrape_main_image_from_page(self, url: str) -> Optional[str]:
        """
        ✅ SCRAPE L'IMAGE PRINCIPALE DEPUIS LA PAGE COMPLÈTE
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Chercher les balises meta Open Graph (meilleure qualité)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']
            
            # Twitter Card
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                return twitter_image['content']
            
            # Image principale de l'article
            article_tag = soup.find('article')
            if article_tag:
                img = article_tag.find('img', class_=lambda x: x and any(c in str(x).lower() for c in ['main', 'hero', 'featured', 'lead']))
                if img and img.get('src'):
                    return img['src']
                
                # Première image de l'article
                img = article_tag.find('img')
                if img and img.get('src'):
                    return img['src']
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to scrape main image from {url}: {e}")
            return None
    
    def scrape_from_newsapi(self, query: str = "technology", max_articles: int = 10) -> List[Dict]:
        """Scrape articles via NewsAPI (nécessite clé API)"""
        if not self.newsapi_key:
            logger.warning("NewsAPI key not provided, skipping NewsAPI scraping")
            return []
        
        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max_articles,
                "apiKey": self.newsapi_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            articles = []
            for item in data.get("articles", []):
                if not item.get('content') or len(item['content'].split()) < 50:
                    continue
                
                # ✅ Obtenir la version HD de l'image
                image_url = item.get('urlToImage')
                if image_url:
                    image_url = self._get_hd_version(image_url)
                
                article = {
                    "title": item.get('title', 'No Title'),
                    "text": item.get('content', item.get('description', '')),
                    "url": item.get('url', ''),
                    "source": item.get('source', {}).get('name', 'NewsAPI'),
                    "published_date": item.get('publishedAt', datetime.now().isoformat()),
                    "image_url": image_url,
                    "scraped_at": datetime.now().isoformat()
                }
                articles.append(article)
            
            logger.info(f"✓ Scraped {len(articles)} articles from NewsAPI")
            return articles
            
        except Exception as e:
            logger.error(f"NewsAPI scraping failed: {e}")
            return []
    
    def scrape_article_full_text(self, url: str) -> Optional[str]:
        """Scrape le texte complet depuis l'URL (si RSS tronqué)"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Supprimer scripts, styles, nav, footer
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            # Chercher le contenu principal
            article_tags = soup.find_all(['article', 'main', 'div'], 
                                        class_=lambda x: x and any(c in str(x).lower() 
                                        for c in ['article', 'content', 'post', 'entry']))
            
            if article_tags:
                text = article_tags[0].get_text(separator=' ', strip=True)
            else:
                # Fallback: tout le body
                text = soup.body.get_text(separator=' ', strip=True) if soup.body else ''
            
            # Validation
            if len(text.split()) > 100:
                logger.info(f"✓ Scraped full article: {len(text.split())} words")
                return text
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to scrape full text from {url}: {e}")
            return None
    
    def download_image(self, image_url: str, save_dir: str = "static/images") -> Optional[str]:
        """
        ✅ TÉLÉCHARGE UNE IMAGE EN HAUTE QUALITÉ
        """
        if not image_url:
            return None
        
        try:
            import os
            os.makedirs(save_dir, exist_ok=True)
            
            # Générer nom unique
            img_hash = hashlib.md5(image_url.encode()).hexdigest()[:12]
            ext = os.path.splitext(urlparse(image_url).path)[1] or '.jpg'
            filename = f"{img_hash}{ext}"
            filepath = os.path.join(save_dir, filename)
            
            # Si l'image existe déjà, ne pas re-télécharger
            if os.path.exists(filepath):
                logger.info(f"✓ Image already exists: {filename}")
                return f"/static/images/{filename}"
            
            # Télécharger
            response = self.session.get(image_url, timeout=10, stream=True)
            response.raise_for_status()
            
            # ✅ OPTIMISER LA QUALITÉ AVEC PIL
            try:
                img_data = BytesIO(response.content)
                img = Image.open(img_data)
                
                # Convertir en RGB si nécessaire
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Sauvegarder en haute qualité
                img.save(filepath, 'JPEG', quality=95, optimize=True)
                
                logger.info(f"✓ Image downloaded and optimized: {filename} ({img.size[0]}x{img.size[1]})")
                return f"/static/images/{filename}"
                
            except Exception as pil_error:
                # Fallback: sauvegarder directement sans optimisation
                logger.warning(f"PIL optimization failed, saving raw: {pil_error}")
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"✓ Image downloaded (raw): {filename}")
                return f"/static/images/{filename}"
            
        except Exception as e:
            logger.warning(f"Failed to download image {image_url}: {e}")
            return None
    
    def scrape_all(self, max_articles: int = 20, use_newsapi: bool = False) -> List[Dict]:
        """Scrape depuis toutes les sources disponibles"""
        all_articles = []
        
        # RSS feeds
        rss_articles = self.scrape_from_rss(max_articles=max_articles)
        all_articles.extend(rss_articles)
        
        # NewsAPI (optionnel)
        if use_newsapi and self.newsapi_key:
            newsapi_articles = self.scrape_from_newsapi(max_articles=max_articles//2)
            all_articles.extend(newsapi_articles)
        
        # Dédupliquer par URL
        seen_urls = set()
        unique_articles = []
        for article in all_articles:
            url = article.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)
        
        logger.info(f"✅ Total scraped: {len(unique_articles)} unique articles")
        return unique_articles[:max_articles]


# ================= TEST =================
if __name__ == "__main__":
    print(">>> Testing NewsScraperBot with HD Images")
    
    bot = NewsScraperBot()
    articles = bot.scrape_all(max_articles=5)
    
    print(f"\n✅ Scraped {len(articles)} articles\n")
    
    for i, article in enumerate(articles[:3], 1):
        print(f"{i}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   Date: {article['published_date']}")
        print(f"   Image: {article['image_url'][:80] if article['image_url'] else 'None'}...")
        print(f"   Text: {article['text'][:100]}...")
        print()