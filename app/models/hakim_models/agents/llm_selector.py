from dotenv import load_dotenv
import os
from langchain_mistralai import ChatMistralAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

def get_best_llm(task):
    if task == "claim_extraction":
        return ChatMistralAI(model="mistral-tiny", api_key=os.environ["hakim_MISTRALAI_API_KEY"])
    elif task == "fact_verification":
        return ChatGroq(model="llama-3.3-70b-versatile", api_key=os.environ["hakim_GROQ_API_KEY"])
    elif task == "scoring":
          model_dir = "./models/deberta_reputation_model_export"
          tokenizer = AutoTokenizer.from_pretrained(model_dir)
          model = AutoModelForSequenceClassification.from_pretrained(model_dir)
          return pipeline("text-classification", model=model, tokenizer=tokenizer)
    elif task == "aggregation":
        return ChatOpenAI(api_key=os.environ["hakim_OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1", model="openrouter/auto")
    else:
        return ChatOpenAI(api_key=os.environ["hakim_OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1", model="openrouter/auto")
