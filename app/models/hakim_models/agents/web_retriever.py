import os
from langchain_community.utilities import SerpAPIWrapper
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

class WebRetrieverAgent:
    def __init__(self):
        try:
            api_key = os.getenv("hakim_SERPAPI_API_KEY")
            if not api_key:
                raise ValueError("SerpAPI key not found. Please set SERPAPI_API_KEY in your environment or .env file.")
            self.search = SerpAPIWrapper(serpapi_api_key=api_key)
            
            # Set up model paths
            self.models_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'models')
            self.reputation_model_path = os.path.join(self.models_dir, 'deberta_reputation_model_export')
            
            # Ensure model directory exists
            if not os.path.exists(self.models_dir):
                os.makedirs(self.models_dir)
                
            logger.info(f"Models directory: {self.models_dir}")
            
        except Exception as e:
            logger.error(f"Error initializing WebRetrieverAgent: {str(e)}")
            raise

    def get_live_evidence(self, claim):
        try:
            results = self.search.results(claim)
            if "organic_results" in results:
                filtered_results = []
                for result in results["organic_results"]:
                    if self._validate_result(result):
                        filtered_results.append(result)
                return filtered_results
            return []
        except Exception as e:
            logger.error(f"Error retrieving evidence: {str(e)}")
            return []
            
    def _validate_result(self, result):
        # Basic validation of search results
        required_fields = ['link', 'snippet']
        return all(field in result for field in required_fields)
