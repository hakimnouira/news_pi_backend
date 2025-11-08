import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from config import REPUTATION_MODEL_PATH

class ReputationScorer:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(REPUTATION_MODEL_PATH)
        self.model = AutoModelForSequenceClassification.from_pretrained(REPUTATION_MODEL_PATH)
        self.model.eval()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
    
    def score_source(self, source_type, source_name):
        """
        Score a source (domain/author) using your trained model
        Args:
            source_type: "News Media", "Author", etc.
            source_name: "cnn.com", "John Smith", etc.
        Returns:
            float: credibility score 1-5
        """
        text = f"{source_type} | {source_name}"
        
        with torch.no_grad():
            inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            outputs = self.model(**inputs)
            score = outputs.logits.cpu().numpy().flatten()[0]
        
        # Clamp score between 1-5
        return max(1.0, min(5.0, float(score)))

# Global instance
reputation_scorer = ReputationScorer()
