import shap
from lime.lime_text import LimeTextExplainer
import numpy as np
from typing import Dict, List, Any

class XAIExplainer:
    """
    Centralized XAI explainer for all agents
    Uses SHAP and LIME (both free and open-source)
    """
    
    def __init__(self):
        self.lime_explainer = LimeTextExplainer(class_names=['fake', 'real'])
        
    def explain_text_classification(self, text: str, predict_fn, method='lime', num_features=10) -> Dict:
        """
        Explain text classification decision
        
        Args:
            text: Input text to explain
            predict_fn: Model prediction function that returns probabilities
            method: 'lime' or 'shap'
            num_features: Number of important features to show
            
        Returns:
            Dictionary with explanation data
        """
        if method == 'lime':
            return self._explain_with_lime(text, predict_fn, num_features)
        else:
            return self._explain_with_shap(text, predict_fn)
    
    def _explain_with_lime(self, text: str, predict_fn, num_features: int) -> Dict:
        """Use LIME for explanation"""
        try:
            exp = self.lime_explainer.explain_instance(
                text,
                predict_fn,
                num_features=num_features
            )
            
            # Get feature importance
            feature_importance = exp.as_list()
            
            # Get prediction probabilities
            proba = predict_fn([text])[0]
            
            return {
                'method': 'LIME',
                'feature_importance': feature_importance,
                'important_words': [feat[0] for feat in feature_importance[:5]],
                'prediction_confidence': float(max(proba)),
                'explanation_html': exp.as_html(),
                'raw_explanation': exp
            }
        except Exception as e:
            return {
                'method': 'LIME',
                'error': str(e),
                'feature_importance': [],
                'important_words': []
            }
    
    def _explain_with_shap(self, text: str, predict_fn) -> Dict:
        """Use SHAP for explanation"""
        try:
            # SHAP works best with model that accepts text directly
            # For your case, we'll use LIME as primary method
            return {'method': 'SHAP', 'note': 'Use LIME for text explanations'}
        except Exception as e:
            return {'method': 'SHAP', 'error': str(e)}
    
    def generate_agent_report(self, agent_name: str, input_data: Any, 
                            output: Dict, explanation: Dict) -> str:
        """
        Generate human-readable report for single agent
        """
        report = f"\n{'='*60}\n"
        report += f"AGENT: {agent_name}\n"
        report += f"{'='*60}\n\n"
        
        report += f"Output Score/Confidence: {output.get('confidence', 'N/A')}\n\n"
        
        if 'feature_importance' in explanation and explanation['feature_importance']:
            report += "Most Important Features:\n"
            for i, (feature, score) in enumerate(explanation['feature_importance'][:5], 1):
                report += f"  {i}. {feature}: {score:+.3f}\n"
        
        report += f"\n{'='*60}\n"
        return report
    
    def aggregate_multi_agent_explanation(self, agent_results: Dict) -> Dict:
        """
        Combine explanations from multiple agents into final explanation
        """
        explanation = {
            'agent_contributions': {},
            'decision_flow': [],
            'important_factors': [],
            'confidence_breakdown': {},
            'final_reasoning': ''
        }
        
        total_weight = 0
        weighted_score = 0
        
        for agent_name, result in agent_results.items():
            if not result:
                continue
                
            score = result.get('score', 0)
            confidence = result.get('confidence', 0)
            weight = result.get('weight', 1.0)
            
            explanation['agent_contributions'][agent_name] = {
                'score': score,
                'confidence': confidence,
                'weight': weight,
                'contribution': score * weight
            }
            
            explanation['confidence_breakdown'][agent_name] = confidence
            
            weighted_score += score * weight
            total_weight += weight
            
            # Track decision flow
            explanation['decision_flow'].append({
                'agent': agent_name,
                'score': score,
                'confidence': confidence
            })
        
        # Calculate final score
        final_score = weighted_score / total_weight if total_weight > 0 else 0.5
        
        # Generate natural language explanation
        explanation['final_reasoning'] = self._generate_reasoning(
            explanation['agent_contributions'],
            final_score
        )
        
        explanation['final_score'] = final_score
        explanation['final_verdict'] = 'REAL' if final_score >= 0.5 else 'FAKE'
        
        return explanation
    
    def _generate_reasoning(self, contributions: Dict, final_score: float) -> str:
        """Generate human-readable explanation"""
        verdict = 'REAL' if final_score >= 0.5 else 'FAKE'
        
        reasoning = f"This news is classified as {verdict} (confidence: {final_score:.1%})\n\n"
        reasoning += "Analysis breakdown:\n\n"
        
        for agent_name, contrib in contributions.items():
            score = contrib['score']
            confidence = contrib['confidence']
            
            # Convert agent name to readable format
            readable_name = agent_name.replace('_', ' ').title()
            
            reasoning += f"• {readable_name}:\n"
            reasoning += f"  - Score: {score:.1%}\n"
            reasoning += f"  - Confidence: {confidence:.1%}\n"
            reasoning += f"  - Impact on final verdict: {contrib['contribution']:.1%}\n\n"
        
        return reasoning
