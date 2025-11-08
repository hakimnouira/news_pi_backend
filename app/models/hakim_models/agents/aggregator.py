from app.models.hakim_models.agents.llm_selector import get_best_llm

class AggregatorAgent:
    def __init__(self):
        self.llm = get_best_llm("aggregation")
    
    def aggregate(self, support_score, source_score, verdict):
        prompt = (
            f"Given:\n"
            f"- Evidence support score: {support_score}/5\n"
            f"- Source credibility score: {source_score}/5\n"
            f"- Verdict: {verdict}\n\n"
            "Rules for combining scores:\n"
            "- If the evidence verdict is 'contradict', the final credibility should be LOW (close to 1.0), unless there is overwhelming supporting evidence elsewhere (not present here).\n"
            "- If the claim is obviously false or the evidence directly refutes the claim, ALWAYS return a low final score, no matter how reputable the source is.\n"
            "- If the verdict is 'support', combine both evidence and source, favoring evidence more heavily.\n"
            "- If the verdict is 'unrelated', result should be neutral: the score should depend mostly on the source, but not exceed 3.0 unless evidence is highly supportive.\n"
            "- Never return a value above 5.0 or below 1.0.\n"
            "- Output ONLY a number, NO explanation."
                )
        try:
            result = self.llm.invoke(prompt)
        except Exception:
            # fallback: simple average if LLM fails (safe)
            return (support_score + source_score) / 2
        if hasattr(result, "content"):
            text = result.content
        else:
            text = str(result)
        
        try:
            score = float(text.strip())
            return max(1.0, min(5.0, score))
        except:
            return (support_score + source_score) / 2
    
def aggregate_with_explanation(self, support_score, source_score, verdict):
    """XAI: Returns final score with detailed breakdown and human-friendly context."""
    final_score = self.aggregate(support_score, source_score, verdict)

    # Show how much each factor matters.
    breakdown_weight_evidence = 60
    breakdown_weight_source = 40
    support_contribution = (support_score / 5.0) * breakdown_weight_evidence
    source_contribution = (source_score / 5.0) * breakdown_weight_source

    # Extra explicit for reporting
    if verdict == 'contradict':
        main_sentence = (
            "The evidence directly contradicts the claim. "
            "When evidence refutes the claim, final credibility should be very low, regardless of source reputation. "
            f"In this case, the evidence scored {support_score}/5 and the source credibility was {source_score:.2f}/5. "
        )
    elif verdict == 'support':
        main_sentence = (
            "The evidence directly supports the claim. "
            "Credibility is mostly determined by this strong evidence, with source reputation also a factor. "
        )
    else:
        main_sentence = (
            "There is limited relevant evidence. "
            "Score mainly reflects source reputation, since evidence is not clear. "
        )

    explanation = (
        f"{main_sentence}Final score is calculated as the average of evidence support ({support_score}/5) "
        f"and source credibility ({source_score:.2f}/5), giving a result of {final_score:.2f}/5 "
        f"({int((final_score / 5.0)*100)}%)."
    )

    verdict_impact = {
        'support': 'Positive: Evidence directly confirms the claim',
        'contradict': 'Negative: Evidence contradicts the claim',
        'unrelated': 'Neutral: Limited relevant evidence found'
    }

    return {
        'final_score': final_score,
        'final_percentage': int((final_score / 5.0) * 100),
        'explanation': explanation,
        'breakdown': {
            'evidence_quality': {
                'score': support_score,
                'contribution': f"{support_contribution:.1f}%",
                'verdict': verdict,
                'impact': verdict_impact.get(verdict, 'Unknown')
            },
            'source_credibility': {
                'score': source_score,
                'contribution': f"{source_contribution:.1f}%"
            }
        }
    }
