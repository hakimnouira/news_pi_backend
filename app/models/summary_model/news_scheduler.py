"""
NewsBot Scheduler - Automatise le scraping, summarization et stockage
Exécution périodique avec APScheduler
"""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import time
import hashlib

# ✅ IMPORTS CORRIGÉS
from .news_scraper import NewsScraperBot
from .db_storage import SummaryStorageManager
from .models.hybrid_summarizer import summarize_bart_llama_title, summarize_full_llama

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)
logger = logging.getLogger(__name__)


class NewsBotScheduler:
    """Planificateur automatique pour le pipeline NewsBot"""
    
    def __init__(
        self,
        interval_hours: int = 6,
        max_articles_per_run: int = 3,
        newsapi_key: str = None
    ):
        self.interval_hours = interval_hours
        self.max_articles = max_articles_per_run
        
        # Initialisation composants
        self.scraper = NewsScraperBot(newsapi_key=newsapi_key)
        self.storage = SummaryStorageManager()
        self.scheduler = BackgroundScheduler()
        
        self.stats = {
            "total_runs": 0,
            "successful_articles": 0,
            "failed_articles": 0,
            "last_run": None
        }
    
    def process_article(self, article: dict) -> bool:
        """Traite un article: summarization + stockage"""
        try:
            logger.info(f"Processing: {article['title'][:50]}...")
            
            # ✅ 1. DÉDUPLICATION AMÉLIORÉE (par URL ET contenu)
            article_url = article.get('url', '')
            content_hash = hashlib.sha256(article['text'].encode('utf-8')).hexdigest()
            
            # Vérifier si l'article existe déjà par URL OU par hash
            existing = self.storage.articles_collection.find_one({
                "$or": [
                    {"source_url": article_url},
                    {"content_hash": content_hash}
                ]
            })
            
            if existing:
                logger.info(f"✓ Article already exists (hash: {content_hash[:12]}...), skipping")
                return False
            
            # ✅ 2. GÉNÉRATION DES 2 MEILLEURS RÉSUMÉS
            logger.info("Generating summaries...")
            
            # Résumé 1: HYBRID (BART + LLaMA Title) - LE MEILLEUR
            summary_hybrid = summarize_bart_llama_title(
                text=article['text'],
                mode="balanced",
                save_to_db=False,
                include_quality_metrics=True
            )
            
            # Résumé 2: FULL LLaMA (pour comparaison)
            # ✅ IMPORT DÉJÀ FAIT EN HAUT DU FICHIER
            summary_llama = summarize_full_llama(
                text=article['text'],
                mode="balanced",
                save_to_db=False,
                include_quality_metrics=True
            )
            
            if not summary_hybrid:
                logger.warning("Hybrid summarization failed")
                return False
            
            # ✅ 3. SAUVEGARDER L'ARTICLE UNE SEULE FOIS
            article_data = {
                "original_text": article['text'],
                "content_hash": content_hash,
                "source_url": article_url,
                "source_name": article.get('source', 'Unknown'),
                "image_url": article.get('image_url', ''),
                "created_at": datetime.now()
            }
            
            article_result = self.storage.articles_collection.insert_one(article_data)
            article_id = str(article_result.inserted_id)
            
            # ✅ 4. SAUVEGARDER LE RÉSUMÉ HYBRID
            self._save_summary(
                article_id=article_id,
                summary_result=summary_hybrid,
                method="hybrid",
                article_metadata={
                    "source_url": article_url,
                    "source_name": article.get('source', 'Unknown'),
                    "image_url": article.get('image_url', '')
                }
            )
            
            # ✅ 5. SAUVEGARDER LE RÉSUMÉ LLAMA FULL (si disponible)
            if summary_llama:
                self._save_summary(
                    article_id=article_id,
                    summary_result=summary_llama,
                    method="llama_full",
                    article_metadata={
                        "source_url": article_url,
                        "source_name": article.get('source', 'Unknown'),
                        "image_url": article.get('image_url', '')
                    }
                )
                logger.info(f"✓ Saved 2 summaries (hybrid + llama_full)")
            else:
                logger.info(f"✓ Saved 1 summary (hybrid only)")
            
            logger.info(f"✓ Article saved: {article_id}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error processing article: {e}", exc_info=True)
            return False
    
    def _save_summary(self, article_id: str, summary_result: dict, method: str, article_metadata: dict):
        """Fonction helper pour sauvegarder un résumé"""
        evaluation_metrics = summary_result.get('metadata', {}).get('evaluation_metrics')
        
        summary_data = {
            "article_id": article_id,
            "method": method,
            "title": summary_result['title'],
            "summary": summary_result['summary'],
            "date_published": summary_result['date_published'],
            "structure_5w1h": summary_result.get('structure_5w1h', {}),
            "key_quotes": summary_result.get('key_quotes', []),
            "entities": summary_result.get('entities', {}),
            "numbers_events": summary_result.get('numbers_events', []),
            "evaluation_metrics": evaluation_metrics,
            "source_url": article_metadata.get('source_url', ''),
            "source_name": article_metadata.get('source_name', 'Unknown'),
            "image_url": article_metadata.get('image_url', ''),
            "created_at": datetime.now()
        }
        
        self.storage.summaries_collection.insert_one(summary_data)
    
    def run_scraping_pipeline(self):
        """Exécute le pipeline complet: scrape → summarize → store"""
        logger.info("="*60)
        logger.info("🚀 STARTING NEWSBOT PIPELINE")
        logger.info("="*60)
        
        start_time = datetime.now()
        self.stats['total_runs'] += 1
        
        try:
            # 1. Scraping
            logger.info(f"Scraping max {self.max_articles} articles...")
            articles = self.scraper.scrape_all(
                max_articles=self.max_articles,
                use_newsapi=bool(self.scraper.newsapi_key)
            )
            
            if not articles:
                logger.warning("No articles scraped, aborting run")
                return
            
            logger.info(f"✓ Found {len(articles)} articles to process")
            
            # 2. Processing
            for i, article in enumerate(articles, 1):
                logger.info(f"\n--- Article {i}/{len(articles)} ---")
                
                success = self.process_article(article)
                
                if success:
                    self.stats['successful_articles'] += 1
                else:
                    self.stats['failed_articles'] += 1
                
                # Rate limiting
                time.sleep(2)
            
            # 3. Statistiques
            duration = (datetime.now() - start_time).total_seconds()
            self.stats['last_run'] = datetime.now().isoformat()
            
            logger.info("="*60)
            logger.info("✅ PIPELINE COMPLETED")
            logger.info(f"   Duration: {duration:.1f}s")
            logger.info(f"   Successful: {self.stats['successful_articles']}")
            logger.info(f"   Failed: {self.stats['failed_articles']}")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
    
    def start(self):
        """Démarre le scheduler"""
        logger.info(f"🤖 NewsBot Scheduler starting...")
        logger.info(f"   Interval: Every {self.interval_hours} hours")
        logger.info(f"   Max articles per run: {self.max_articles}")
        
        # Exécution immédiate au démarrage
        logger.info("Running initial scraping...")
        self.run_scraping_pipeline()
        
        # Planification périodique
        self.scheduler.add_job(
            func=self.run_scraping_pipeline,
            trigger=IntervalTrigger(hours=self.interval_hours),
            id='newsbot_scraper',
            name='NewsBot Scraping Pipeline',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("✅ Scheduler started successfully")
    
    def stop(self):
        """Arrête le scheduler"""
        self.scheduler.shutdown()
        self.storage.close()
        logger.info("🛑 Scheduler stopped")
    
    def get_stats(self) -> dict:
        """Retourne les statistiques"""
        return self.stats