from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class TextVerificationRequest(BaseModel):
    text: str
    include_explanation: bool = True

class VerificationResponse(BaseModel):
    claims: List[str]
    best_evidence: str
    best_url: str
    source_domain: str
    source_credibility_score: float
    verdict: str
    final_credibility_score: float
    all_sources: List[Dict[str, Any]]
    explanation: Optional[Dict[str, Any]] = None