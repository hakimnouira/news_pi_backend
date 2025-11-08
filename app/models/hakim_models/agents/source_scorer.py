import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import shap

class SourceScorerAgent:
    def __init__(self):
        # Path to your finetuned DeBERTa model
        model_path = "app\models\hakim_models\models\deberta_reputation_model_export"
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.eval()
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        
        print(f"Source scoring model loaded on: {self.device}")
    
    def score_source(self, source_type, source_name):
        """
        Score a source using your trained DeBERTa model.
        
        Args:
            source_type: "Web", "News Media", etc. (can be ignored if not used in training)
            source_name: "cnn.com", "bbc.com", etc.
        
        Returns:
            float: credibility score 1-5
        """
        # Format input based on your training data format
        # If you trained with just the domain:
        text = source_name
        
        # If you trained with "source_type | source_name" format:
        # text = f"{source_type} | {source_name}"
        
        with torch.no_grad():
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                truncation=True, 
                max_length=128,
                padding=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            outputs = self.model(**inputs)
            logits = outputs.logits.cpu().numpy().flatten()
            
            # If your model outputs a single regression value:
            score = float(logits[0])
            
            # If your model outputs class probabilities (5 classes for scores 1-5):
            # predicted_class = logits.argmax()
            # score = float(predicted_class + 1)  # Convert 0-4 to 1-5
        
        # Clamp score between 1-5
        return max(1.0, min(5.0, score))
    def explain_source_with_shap(self, source_type, source_name, num_features=10):
        """
        Use SHAP to explain a model prediction for a given source.
        Returns the most influential tokens and their SHAP scores.
        """
        text = source_name
        # text = f"{source_type} | {source_name}" # if you trained this way

        # Build a prediction function for SHAP that outputs model scores
        def predict_proba(texts):
            all_scores = []
            for t in texts:
                inputs = self.tokenizer(
                    t, return_tensors="pt", truncation=True, max_length=128, padding=True
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits.cpu().numpy().flatten()[0] # regression (score)
                all_scores.append([logits])
            return np.array(all_scores)

        # Main SHAP call
        explainer = shap.Explainer(predict_proba, self.tokenizer)
        shap_values = explainer([text])
        # Get explanation for first (and only) input
        tok_exp = sorted(
            zip(shap_values.data[0], shap_values.values[0]),
            key=lambda x: -abs(x[1])
        )
        # Get top tokens
        top = tok_exp[:num_features]
        explanation = [
            {"token": t, "contribution": float(c)} for t, c in top
        ]
        return explanation