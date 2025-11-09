"""
Module de stockage MongoDB pour articles et résumés
Version améliorée avec support images et métadonnées NewsBot
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError, ConnectionFailure
import hashlib

# === CONFIG LOGGING ===
logging.basicConfig(level=logging.INFO, force=True)
logging.getLogger().addHandler(logging.StreamHandler())

class SummaryStorageManager:
    """Gestionnaire de stockage pour articles et résumés"""
    
    def __init__(self, connection_string: str = "mongodb+srv://User1:NN12345678@cluster1.axkvwwm.mongodb.net/news_summarizer_db?retryWrites=true&w=majority"):
        """Initialise la connexion MongoDB Atlas"""
        try:
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=5000,
                maxPoolSize=50,
                retryWrites=True
            )
            
            # Test connexion
            self.client.server_info()
            
            self.db = self.client["news_summarizer_db"]
            self.articles_collection = self.db["articles"]
            self.summaries_collection = self.db["summaries"]
            self.evaluations_collection = self.db["evaluations"]
            
            self._create_indexes()
            logging.info("✅ MongoDB Atlas connection established")
            
        except ConnectionFailure as e:
            logging.error(f"❌ MongoDB connection failed: {e}")
            raise
             
    def _create_indexes(self):
        """Crée les index"""
        try:
            self.articles_collection.create_index([("content_hash", ASCENDING)], unique=True)
            self.articles_collection.create_index([("created_at", DESCENDING)])
            self.articles_collection.create_index([("language", ASCENDING)])
            self.articles_collection.create_index([("source_name", ASCENDING)])  # NOUVEAU
            self.articles_collection.create_index([("source_url", ASCENDING)])   # NOUVEAU
            
            self.summaries_collection.create_index([("article_id", ASCENDING)])
            self.summaries_collection.create_index([("method", ASCENDING)])
            self.summaries_collection.create_index([("created_at", DESCENDING)])
            self.summaries_collection.create_index([("metadata.overall_score", DESCENDING)])
            self.summaries_collection.create_index([("source_name", ASCENDING)])  # NOUVEAU
            
            # ===== INDEX TEXTUEL POUR LA RECHERCHE =====
            self.summaries_collection.create_index(
                [("title", "text"), ("summary", "text")],
                weights={"title": 5, "summary": 1},
                default_language="english"
            )
            
            self.evaluations_collection.create_index([("article_id", ASCENDING)])
            self.evaluations_collection.create_index([("created_at", DESCENDING)])
            
            logging.info("✅ Indexes created successfully")
        except Exception as e:
            logging.warning(f"⚠️ Index creation warning: {e}")
    
    def _generate_content_hash(self, text: str) -> str:
        """Génère un hash unique pour le contenu"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def save_article_with_summary(
        self,
        original_text: str,
        summary_result: Dict,
        method: str,
        evaluation_metrics: Optional[Dict] = None
    ) -> Dict[str, str]:
        """
        Sauvegarde un article avec son résumé et évaluation
        Version améliorée avec support images et métadonnées NewsBot
        """
        try:
            content_hash = self._generate_content_hash(original_text)
            
            # === ARTICLE DOCUMENT (avec nouveaux champs) ===
            article_doc = {
                "content_hash": content_hash,
                "original_text": original_text,
                "word_count": len(original_text.split()),
                "language": summary_result.get('metadata', {}).get('language', 'unknown'),
                "date_extracted": summary_result.get('date_published', 'Not specified'),
                
                # NOUVEAUX CHAMPS NEWSBOT
                "source_url": summary_result.get('source_url', ''),
                "source_name": summary_result.get('source_name', 'Unknown'),
                "image_url": summary_result.get('image_url', ''),
                "original_title": summary_result.get('original_title', ''),
                
                "created_at": datetime.now(),
                "last_updated": datetime.now()
            }
            
            # Insertion avec gestion duplicata
            try:
                result = self.articles_collection.update_one(
                    {"content_hash": content_hash},
                    {"$setOnInsert": article_doc},
                    upsert=True
                )
                
                if result.upserted_id:
                    article_id = str(result.upserted_id)
                    logging.info(f"✅ New article saved: {article_id}")
                else:
                    existing = self.articles_collection.find_one({"content_hash": content_hash})
                    article_id = str(existing['_id'])
                    logging.info(f"ℹ️ Article already exists: {article_id}")
            except DuplicateKeyError:
                existing = self.articles_collection.find_one({"content_hash": content_hash})
                article_id = str(existing['_id'])
                logging.info(f"ℹ️ Duplicate article: {article_id}")
            
            # === SUMMARY DOCUMENT (avec nouveaux champs) ===
            summary_doc = {
                "article_id": article_id,
                "method": method,
                "title": summary_result.get('title', ''),
                "summary": summary_result.get('summary', ''),
                "date_published": summary_result.get('date_published', 'Not specified'),
                "structure_5w1h": summary_result.get('structure_5w1h', {}),
                "key_quotes": summary_result.get('key_quotes', []),
                "entities": summary_result.get('entities', {}),
                "numbers_events": summary_result.get('numbers_events', {}),
                "metadata": {
                    **summary_result.get('metadata', {}),
                    "method": method
                },
                "evaluation_metrics": evaluation_metrics,
                
                # NOUVEAUX CHAMPS NEWSBOT
                "image_url": summary_result.get('image_url', ''),
                "source_url": summary_result.get('source_url', ''),
                "source_name": summary_result.get('source_name', 'Unknown'),
                "original_title": summary_result.get('original_title', ''),
                
                "created_at": datetime.now()
            }
            
            summary_insert = self.summaries_collection.insert_one(summary_doc)
            summary_id = str(summary_insert.inserted_id)
            logging.info(f"✅ Summary saved: {summary_id} (method: {method})")
            
            # === EVALUATION DOCUMENT (si fourni) ===
            if evaluation_metrics:
                evaluation_doc = {
                    "article_id": article_id,
                    "summary_id": summary_id,
                    "method": method,
                    "metrics": evaluation_metrics,
                    "overall_score": evaluation_metrics.get('overall_score', 0),
                    "created_at": datetime.now()
                }
                self.evaluations_collection.insert_one(evaluation_doc)
                logging.info("✅ Evaluation saved")
            
            return {"article_id": article_id, "summary_id": summary_id, "status": "success"}
        
        except Exception as e:
            logging.error(f"❌ Error saving to MongoDB: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_recent_summaries(self, limit: int = 20, source: Optional[str] = None) -> List[Dict]:
        """
        Récupère les résumés récents avec filtre optionnel par source
        NOUVEAU: Support filtrage par source
        """
        try:
            query = {}
            if source:
                query["source_name"] = source
            
            summaries = self.summaries_collection.find(query).sort("created_at", -1).limit(limit)
            
            result = []
            for summary in summaries:
                result.append({
                    "summary_id": str(summary["_id"]),
                    "article_id": summary["article_id"],
                    "method": summary["method"],
                    "title": summary["title"],
                    "summary": summary["summary"],
                    "date_published": summary["date_published"],
                    "image_url": summary.get("image_url", ""),
                    "source_name": summary.get("source_name", "Unknown"),
                    "source_url": summary.get("source_url", ""),
                    "created_at": summary["created_at"]
                })
            
            logging.info(f"📊 Fetched {len(result)} summaries")
            return result
            
        except Exception as e:
            logging.error(f"❌ Error fetching summaries: {e}")
            return []
    
    def get_statistics(self) -> Dict:
        """Récupère des statistiques globales"""
        try:
            stats = {
                "total_articles": self.articles_collection.count_documents({}),
                "total_summaries": self.summaries_collection.count_documents({}),
                "total_evaluations": self.evaluations_collection.count_documents({}),
                
                # NOUVELLES STATS
                "articles_by_source": list(self.summaries_collection.aggregate([
                    {"$group": {"_id": "$source_name", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 10}
                ])),
                "articles_with_images": self.summaries_collection.count_documents(
                    {"image_url": {"$ne": ""}}
                ),
                "recent_24h": self.summaries_collection.count_documents({
                    "created_at": {"$gte": datetime.now().replace(hour=0, minute=0, second=0)}
                })
            }
            
            logging.info("📊 Statistics retrieved")
            return stats
        except Exception as e:
            logging.error(f"❌ Error getting statistics: {e}")
            return {}
    
    def close(self):
        """Ferme la connexion MongoDB"""
        try:
            self.client.close()
            logging.info("🔒 MongoDB connection closed")
        except Exception as e:
            logging.error(f"❌ Error closing connection: {e}")


# ================= TEST RAPIDE =================

if __name__ == "__main__":
    print(">>> Testing db_storage.py with NewsBot features")
    
    try:
        storage = SummaryStorageManager()
        print("✅ MongoDB connection established successfully.")
        
        test_article = "This is a test article about artificial intelligence..."
        test_summary = {
            "title": "AI Test Article",
            "summary": "A brief summary of the article.",
            "date_published": "October 24, 2025",
            "metadata": {"language": "en", "processing_time": 1.5},
            "entities": {"PERSON": ["John"], "ORG": ["TechCorp"]},
            "key_quotes": [],
            "structure_5w1h": {},
            
            # Nouveaux champs NewsBot
            "source_url": "https://example.com/article",
            "source_name": "TechNews",
            "image_url": "https://example.com/image.jpg",
            "original_title": "Original Article Title"
        }
        
        result = storage.save_article_with_summary(
            original_text=test_article,
            summary_result=test_summary,
            method="test"
        )
        print(f"✅ Test save result: {result}")
        
        stats = storage.get_statistics()
        print(f"📊 Stats: {stats}")
        
        storage.close()
        print("🔒 Test completed successfully.")
    
    except Exception as e:
        print(f"❌ Storage test failed: {e}")
