"""
Pydantic Models pour le module Summarizer
Peut être utilisé pour validation et documentation API
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class SummaryBase(BaseModel):
    title: str
    summary: str
    method: str
    date_published: str

class SummaryCreate(SummaryBase):
    article_id: str
    structure_5w1h: Optional[Dict] = None
    key_quotes: Optional[List[str]] = None
    entities: Optional[Dict] = None

class SummaryInDB(SummaryBase):
    summary_id: str
    article_id: str
    overall_score: Optional[float] = None
    created_at: datetime
    image_url: Optional[str] = ""
    source_name: Optional[str] = "Unknown"
    source_url: Optional[str] = ""

    class Config:
        from_attributes = True

class ArticleBase(BaseModel):
    original_text: str
    source_name: Optional[str] = "Unknown"
    source_url: Optional[str] = ""
    image_url: Optional[str] = ""

class ArticleCreate(ArticleBase):
    pass

class ArticleInDB(ArticleBase):
    article_id: str
    summaries: List[SummaryInDB]
    created_at: datetime
    xai_explanation: Optional[Dict] = None
    xai_cached: bool = False

    class Config:
        from_attributes = True

class XAIRequest(BaseModel):
    article_id: str

class XAIResponse(BaseModel):
    status: str
    message: str
    xai_explanation: Optional[Dict] = None

class BotStats(BaseModel):
    total_runs: int = 0
    successful_articles: int = 0
    failed_articles: int = 0
    last_run: Optional[str] = None
    status: str = "inactive"

class GlobalStats(BaseModel):
    total_articles: int
    total_summaries: int
    articles_by_source: List[Dict]
    articles_with_images: int
    recent_24h: int

class SummarizeRequest(BaseModel):
    """Pour une future fonctionnalité de summarization à la demande"""
    text: str
    method: str = Field(default="hybrid", description="Method: hybrid, llama_full, or bart")
    mode: str = Field(default="balanced", description="Mode: short, balanced, or detailed")
    include_xai: bool = Field(default=False, description="Generate XAI explanation")

class SummarizeResponse(BaseModel):
    success: bool
    article_id: Optional[str] = None
    summaries: List[SummaryInDB]
    xai_explanation: Optional[Dict] = None
    error: Optional[str] = None