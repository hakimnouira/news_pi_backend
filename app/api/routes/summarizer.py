"""
Summarizer API Router
Endpoints pour résumés d'articles avec XAI
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
import logging

# Imports des modules du summarizer
from app.models.summary_model.db_storage import SummaryStorageManager
from app.models.summary_model.news_scheduler import NewsBotScheduler
from app.models.summary_model.xai_explainer import RealXAIExplainer

router = APIRouter()
logger = logging.getLogger(__name__)

# ===== VARIABLES GLOBALES =====
storage: Optional[SummaryStorageManager] = None
newsbot: Optional[NewsBotScheduler] = None
xai_explainer: Optional[RealXAIExplainer] = None

# ===== INITIALISATION (appelée au startup) =====
def init_summarizer_services():
    """Initialise les services du summarizer"""
    global storage, newsbot, xai_explainer
    
    try:
        storage = SummaryStorageManager()
        logger.info("✅ SummaryStorageManager initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize storage: {e}")
        storage = None
    
    try:
        xai_explainer = RealXAIExplainer()
        logger.info("✅ XAI Explainer initialized")
    except Exception as e:
        logger.error(f"⚠️ Failed to initialize XAI: {e}")
        xai_explainer = None
    
    try:
        newsbot = NewsBotScheduler(
            interval_hours=6,
            max_articles_per_run=10,
            newsapi_key=None
        )
        newsbot.start()
        logger.info("✅ NewsBot Scheduler started")
    except Exception as e:
        logger.error(f"⚠️ Failed to initialize NewsBot: {e}")
        newsbot = None

def shutdown_summarizer_services():
    """Arrête les services du summarizer"""
    global newsbot, storage
    
    if newsbot:
        newsbot.stop()
        logger.info("🛑 NewsBot stopped")
    
    if storage:
        storage.close()
        logger.info("🛑 Storage closed")

# ===== PYDANTIC MODELS =====
class SummaryResponse(BaseModel):
    summary_id: str
    article_id: str
    method: str
    title: str
    summary: str
    date_published: str
    overall_score: Optional[float] = None
    created_at: datetime
    image_url: Optional[str] = ""
    source_name: Optional[str] = "Unknown"
    source_url: Optional[str] = ""

class ArticleResponse(BaseModel):
    article_id: str
    original_text: str
    summaries: List[SummaryResponse]
    created_at: datetime
    image_url: Optional[str] = ""
    source_name: Optional[str] = "Unknown"
    source_url: Optional[str] = ""
    xai_explanation: Optional[dict] = None
    xai_cached: bool = False

class BotStatsResponse(BaseModel):
    total_runs: int
    successful_articles: int
    failed_articles: int
    last_run: Optional[str] = None
    status: str

class GlobalStatsResponse(BaseModel):
    total_articles: int
    total_summaries: int
    articles_by_source: List[dict]
    articles_with_images: int
    recent_24h: int

# ===== ENDPOINTS =====

@router.get("/", tags=["summarizer"])
def health_check():
    """Health check du module summarizer"""
    return {
        "status": "ok",
        "message": "Summarizer API is running",
        "storage": "connected" if storage else "disconnected",
        "newsbot": "active" if newsbot else "inactive",
        "xai": "available" if xai_explainer else "unavailable"
    }

@router.get("/summaries", response_model=List[SummaryResponse], tags=["summarizer"])
def get_summaries(
    limit: int = 20,
    skip: int = 0,
    source: Optional[str] = None,
    method: Optional[str] = "hybrid",
    search: Optional[str] = None
):
    """Récupère les résumés avec filtres"""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    try:
        query = {}
        if source:
            query["source_name"] = source
        if method and method != "all":
            query["method"] = method
        
        # Recherche par mots-clés
        if search:
            search_regex = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"title": search_regex},
                {"summary": search_regex},
                {"source_name": search_regex}
            ]
            logger.info(f"🔍 Search: {search}")
        
        summaries_cursor = storage.summaries_collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        result = []
        
        for summary in summaries_cursor:
            evaluation_metrics = summary.get("evaluation_metrics")
            overall_score = evaluation_metrics.get("overall_score") if isinstance(evaluation_metrics, dict) else None
            
            result.append(SummaryResponse(
                summary_id=str(summary["_id"]),
                article_id=summary["article_id"],
                method=summary["method"],
                title=summary["title"],
                summary=summary["summary"],
                date_published=summary["date_published"],
                overall_score=overall_score,
                created_at=summary["created_at"],
                image_url=summary.get("image_url", ""),
                source_name=summary.get("source_name", "Unknown"),
                source_url=summary.get("source_url", "")
            ))
        
        logger.info(f"📊 Fetched {len(result)} summaries (method={method}, search={search})")
        return result
        
    except Exception as e:
        logger.error(f"❌ Error fetching summaries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/articles/{article_id}", response_model=ArticleResponse, tags=["summarizer"])
def get_article(article_id: str):
    """Récupère un article complet avec ses résumés"""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    try:
        try:
            obj_id = ObjectId(article_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid article ID")
        
        article = storage.articles_collection.find_one({"_id": obj_id})
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        # Récupérer les résumés
        summaries_cursor = storage.summaries_collection.find({
            "article_id": article_id,
            "method": {"$in": ["hybrid", "llama_full"]}
        }).sort([("method", 1)])
        
        summary_list = []
        for summary in summaries_cursor:
            evaluation_metrics = summary.get("evaluation_metrics")
            overall_score = evaluation_metrics.get("overall_score") if isinstance(evaluation_metrics, dict) else None
            
            summary_list.append(SummaryResponse(
                summary_id=str(summary["_id"]),
                article_id=summary["article_id"],
                method=summary["method"],
                title=summary["title"],
                summary=summary["summary"],
                date_published=summary["date_published"],
                overall_score=overall_score,
                created_at=summary["created_at"],
                image_url=summary.get("image_url", ""),
                source_name=summary.get("source_name", "Unknown"),
                source_url=summary.get("source_url", "")
            ))
        
        # Mettre hybrid en premier
        summary_list.sort(key=lambda x: (x.method != "hybrid", x.created_at))
        
        # Vérifier si XAI existe
        xai_explanation = article.get("xai_explanation")
        xai_cached = xai_explanation is not None
        
        return ArticleResponse(
            article_id=str(article["_id"]),
            original_text=article["original_text"],
            summaries=summary_list,
            created_at=article["created_at"],
            image_url=article.get("image_url", ""),
            source_name=article.get("source_name", "Unknown"),
            source_url=article.get("source_url", ""),
            xai_explanation=xai_explanation,
            xai_cached=xai_cached
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ Error fetching article {article_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/articles/{article_id}/generate-xai", tags=["summarizer"])
def generate_xai_explanation(article_id: str):
    """Génère l'explication XAI à la demande"""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    if not xai_explainer:
        raise HTTPException(status_code=503, detail="XAI not available")
    
    try:
        try:
            obj_id = ObjectId(article_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid article ID")
        
        article = storage.articles_collection.find_one({"_id": obj_id})
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        
        # Vérifier si XAI existe déjà
        if article.get("xai_explanation"):
            logger.info(f"XAI already cached for {article_id}")
            return {
                "status": "cached",
                "message": "XAI already exists",
                "xai_explanation": article["xai_explanation"]
            }
        
        # Récupérer le meilleur résumé
        summary = storage.summaries_collection.find_one({
            "article_id": article_id,
            "method": "hybrid"
        })
        
        if not summary:
            summary = storage.summaries_collection.find_one({
                "article_id": article_id,
                "method": "llama_full"
            })
        
        if not summary:
            raise HTTPException(status_code=404, detail="No summary found")
        
        logger.info(f"🔬 Generating XAI for {article_id}...")
        
        # Préparer données
        summary_dict = {
            "title": summary.get("title", ""),
            "summary": summary.get("summary", ""),
            "entities": summary.get("entities", {}),
            "key_quotes": summary.get("key_quotes", []),
            "structure_5w1h": summary.get("structure_5w1h", {}),
            "metadata": {
                "evaluation_metrics": summary.get("evaluation_metrics", {"overall_score": 0.75})
            }
        }
        
        # GÉNÉRER XAI
        xai_explanation = xai_explainer.explain_summary_comprehensive(
            article["original_text"],
            summary_dict,
            summary.get("method", "hybrid")
        )
        
        # SAUVEGARDER en cache
        storage.articles_collection.update_one(
            {"_id": obj_id},
            {"$set": {
                "xai_explanation": xai_explanation,
                "xai_generated_at": datetime.utcnow()
            }}
        )
        
        logger.info(f"✅ XAI generated and cached for {article_id}")
        
        return {
            "status": "generated",
            "message": "XAI generated successfully",
            "xai_explanation": xai_explanation
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"❌ XAI generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"XAI failed: {str(e)}")

@router.get("/bot/stats", response_model=BotStatsResponse, tags=["summarizer"])
def get_bot_stats():
    """Statistiques du NewsBot"""
    if not newsbot:
        raise HTTPException(status_code=503, detail="NewsBot not initialized")
    
    try:
        stats = newsbot.get_stats()
        return BotStatsResponse(
            total_runs=stats.get('total_runs', 0),
            successful_articles=stats.get('successful_articles', 0),
            failed_articles=stats.get('failed_articles', 0),
            last_run=stats.get('last_run'),
            status="active"
        )
    except Exception as e:
        logger.error(f"❌ Error fetching bot stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/bot/trigger", tags=["summarizer"])
def trigger_scraping():
    """Déclenche manuellement le scraping"""
    if not newsbot:
        raise HTTPException(status_code=503, detail="NewsBot not initialized")
    
    try:
        import threading
        thread = threading.Thread(target=newsbot.run_scraping_pipeline)
        thread.start()
        logger.info("🚀 Manual scraping triggered")
        return {"status": "triggered", "message": "Scraping started in background"}
    except Exception as e:
        logger.error(f"❌ Error triggering scraping: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/stats", response_model=GlobalStatsResponse, tags=["summarizer"])
def get_global_stats():
    """Statistiques globales de la base de données"""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    try:
        stats = storage.get_statistics()
        logger.info("📊 Global stats retrieved")
        return GlobalStatsResponse(**stats)
    except Exception as e:
        logger.error(f"❌ Error fetching global stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")