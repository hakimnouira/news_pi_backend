from app.models.hakim_models.agents.llm_selector import get_best_llm
import re 


class ClaimExtractorAgent:
    def __init__(self):
        self.llm = get_best_llm("claim_extraction")

    def extract_claims(self, article_text):
        prompt = (
            "You are an expert fact-checking assistant. Extract ONLY verifiable, objective, and discrete factual statements from the news article below.\n\n"
            "Requirements:\n"
            "- Each claim must be atomic (one fact per line)\n"
            "- Claims must be independently verifiable through credible sources\n"
            "- Do NOT include opinions, speculation, hypotheticals, quotes, future tense, or inferences\n"
            "- Ignore any statement that uses words like 'might', 'could', 'expected to', 'reportedly', 'sources say', 'rumored', 'if', or is conditional/hypothetical\n"
            "- Do NOT include duplicated information\n"
            "- Do NOT number the claims\n"
            "- List each claim on a separate line\n"
            "- If no verifiable factual claims exist, respond with exactly: NONE\n\n"
            f"Article:\n{article_text}\n\n"
            "Extracted Claims (one per line):\n"
        )
        
        result = self.llm.invoke(prompt)
        
        if hasattr(result, "content"):
            text = result.content
        elif isinstance(result, dict) and "content" in result:
            text = result["content"]
        else:
            text = str(result)
        
        claims = [
            line.strip() 
            for line in text.split('\n') 
            if line.strip() and line.strip().upper() != 'NONE'
        ]
        
        return claims if claims else None

    def extract_claims_with_explanation(self, article_text):
        """
        XAI: Returns list of claims, high-level explanation,
        and (for each claim) tokens supporting it as a factual statement.
        """
        claims = self.extract_claims(article_text)

        def overlap_terms(claim, article_text, topk=5):
            article_terms = set(re.findall(r"\w+", article_text.lower()))
            claim_terms = set(re.findall(r"\w+", claim.lower()))
            overlap = list(claim_terms & article_terms)
            return sorted(overlap, key=len, reverse=True)[:topk]
        
        if not claims:
            return {
                'claims': [],
                'explanation': 'No verifiable factual claims found in the text. The content may be purely opinion-based or lacks concrete statements.',
                'claim_details': []
            }
        
        explanation = f"Identified {len(claims)} verifiable claim(s) from the article. These are atomic, fact-based statements that can be independently verified."

        claim_details = []
        for claim in claims:
            key_terms = overlap_terms(claim, article_text)
            claim_details.append({
                'claim': claim,
                'reason': "Contains a factual assertion found in the article and is independently verifiable.",
                'highlighted_terms': key_terms
            })

        return {
            'claims': claims,
            'explanation': explanation,
            'claim_details': claim_details
        }
