from fastapi import APIRouter, HTTPException, UploadFile, File
import os
import tempfile
import logging
from urllib.parse import urlparse
from app.models.newscheck import VerificationResponse, TextVerificationRequest  # Add this import

from app.models.hakim_models.agents.claim_extractor import ClaimExtractorAgent
from app.models.hakim_models.agents.evidence_retriever import EvidenceRetrieverAgent
from app.models.hakim_models.agents.cross_verifier import CrossVerifierAgent
from app.models.hakim_models.agents.source_scorer import SourceScorerAgent
from app.models.hakim_models.agents.aggregator import AggregatorAgent
from app.models.hakim_models.agents.web_retriever import WebRetrieverAgent
from app.models.hakim_models.agents.image_to_text import ImageToTextAgent




router = APIRouter()

# Instantiate agents used by the handlers (adjust constructors if they require config)
claim_agent = ClaimExtractorAgent()
web_agent = WebRetrieverAgent()
verifier_agent = CrossVerifierAgent()
source_agent = SourceScorerAgent()
aggregator_agent = AggregatorAgent()
image_agent = ImageToTextAgent()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_social_platform(url: str) -> bool:
    # simple domain-based filter for common social sites
    if not url:
        return False
    netloc = urlparse(url).netloc.lower()
    social_domains = ("twitter.com", "facebook.com", "instagram.com", "youtube.com", "t.me", "reddit.com")
    return any(d in netloc for d in social_domains)

def format_source_for_model(url: str) -> str:
    # return domain only for scoring/formatting purposes
    if not url:
        return ""
    return urlparse(url).netloc.lower()

@router.get("/")
def health_check():
    return {"status": "ok", "message": "Fact Checking API with XAI is running"}

@router.post("/verify/text", response_model=VerificationResponse)
def verify_text(request: TextVerificationRequest):
    try:
        # 1. Extract claims WITH XAI
        if not request.text:
            raise HTTPException(status_code=400, detail="Input text cannot be empty")

        claim_result = claim_agent.extract_claims_with_explanation(request.text)
        claims = claim_result.get('claims', [])
        if not claims:
            raise HTTPException(status_code=400, detail="No verifiable claims found in the text")
        claim_explanation = claim_result

        claim = claims[0]

        # 2. Pure web retrieval (no RAG)
        web_results = web_agent.get_live_evidence(claim)
        if not web_results:
            raise HTTPException(status_code=404, detail="No evidence found from web sources")

        rag_docs = [{
            "source": r.get("link", ""),
            "title": r.get("title", ""),
            "snippet": r.get("snippet", ""),
            "similarity": 1.0,
            "weight": 1.0,
            "query_variant": claim,
            "metadata": {}
        } for r in web_results if not is_social_platform(r.get("link", ""))]

        if not rag_docs:
            raise HTTPException(status_code=404, detail="No valid news sources found after filtering social media")

        # 3. Cross verification WITH XAI
        all_sources_data = []
        for evidence in rag_docs:
            snippet = evidence.get("snippet", "")
            url = evidence.get("source", "")
            verdict_result = verifier_agent.verify_claim_with_explanation(claim, snippet)
            all_sources_data.append({
                "url": url,
                "snippet": snippet,
                "verdict": verdict_result["verdict"],
                "explanation": verdict_result["explanation"],
                "highlighted_terms": verdict_result.get("highlighted_terms", []),
                "source_title": evidence.get("title", ""),
                "metadata": evidence.get("metadata", {}),
                "similarity": evidence.get("similarity"),
                "weight": evidence.get("weight"),
                "query_variant": evidence.get("query_variant")
            })

        # 4. Pick best source for UI
        if not all_sources_data:
            raise HTTPException(status_code=404, detail="No valid news sources or evidence found.")

        best = max(
            all_sources_data,
            key=lambda s: {'support': 2, 'contradict': 1, 'unrelated': 0}.get(s["verdict"], 0)
        )
        formatted_source = format_source_for_model(best["url"])

        # 5. Source credibility WITH XAI
        if hasattr(source_agent, 'score_source_with_explanation'):
            source_result = source_agent.score_source_with_explanation("Web", formatted_source)
            source_score = source_result['score']
            source_explanation = source_result
        else:
            source_score = source_agent.score_source("Web", formatted_source)
            source_explanation = {
                'score': source_score,
                'explanation': f'Source credibility: {source_score}/5',
                'contributing_factors': ['Domain reputation'],
                'is_trusted': source_score >= 4.0
            }

        # 6. Aggregate final credibility WITH XAI
        support_score = 4 if best["verdict"] == "support" else 1
        adjusted_source_score = source_score
        if best["verdict"] == "contradict":
             adjusted_source_score = 5.0 - source_score  # Invert the source trust
        
        if hasattr(aggregator_agent, 'aggregate_with_explanation'):
            aggregation_result = aggregator_agent.aggregate_with_explanation(
                support_score, source_score, best["verdict"]
            )
            final_score = aggregation_result['final_score']
            aggregation_explanation = aggregation_result
        else:
            final_score = aggregator_agent.aggregate(support_score, adjusted_source_score, best["verdict"])
            aggregation_explanation = {
                'final_score': final_score,
                'explanation': f'Combined evidence ({support_score}/5) and source credibility ({adjusted_source_score}/5)',
                'breakdown': {
                    'evidence_quality': {'score': support_score, 'verdict': best["verdict"]},
                    'source_credibility': {'score': adjusted_source_score}
                }
            }

        # 7. Build XAI explanation
        explanation = {
            "claim_extraction": claim_explanation,
            "evidence_retrieval": {
                "web_sources_count": len(rag_docs),
                "valid_news_sources": len(all_sources_data)
            },
            "best_evidence_selection": {
                "chosen_source": best["url"],
                "verdict_explanation": best["explanation"],
                "highlighted_terms": best.get("highlighted_terms"),
                "query_variant": best.get("query_variant"),
                "similarity": best.get("similarity"),
                "weight": best.get("weight"),
                "source_title": best.get("source_title"),
            },
            "source_credibility": source_explanation,
            "final_calculation": aggregation_explanation
        }

        return VerificationResponse(
            claims=claims,
            best_evidence=best["snippet"],
            best_url=best["url"],
            source_domain=formatted_source,
            source_credibility_score=source_score,
            verdict=best["verdict"],
            final_credibility_score=final_score,
            all_sources=all_sources_data,
            explanation=explanation
        )

    except HTTPException as he:
        logger.warning(f"HTTP Exception: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in verify_text: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/verify/image", response_model=VerificationResponse)
async def verify_image(file: UploadFile = File(...), include_explanation: bool = True):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")

        # Check file size (e.g., limit to 10MB)
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="File size too large. Maximum size is 10MB")

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name

        try:
            text = image_agent.extract_text_from_file(tmp_file_path)
            if not text:
                raise HTTPException(status_code=400, detail="No text could be extracted from the image")
            
            request = TextVerificationRequest(text=text, include_explanation=include_explanation)
            return verify_text(request)
        finally:
            try:
                os.unlink(tmp_file_path)
            except Exception as e:
                logger.error(f"Error deleting temporary file: {str(e)}")
    except HTTPException as he:
        logger.warning(f"HTTP Exception in verify_image: {str(he)}")
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in verify_image: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
