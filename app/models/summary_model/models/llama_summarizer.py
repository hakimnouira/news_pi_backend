"""
Llama Summarizer Module
Utilise LLaMA 3.3 70B via Grok API pour générer des résumés et titres accrocheurs
"""

import logging
import re
from typing import Optional, Dict
from groq import Groq

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Client Grok
client = Groq()

def call_llama_grok(prompt: str, temperature: float = 1, max_tokens: int = 1024) -> Optional[str]:
    """
    Appelle le modèle LLaMA 3.3 70B via Grok API.
    """
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_completion_tokens=max_tokens,
            top_p=1,
            stream=False,
            stop=None
        )
        response = completion.choices[0].message.content
        logging.info(f"LLaMA response received ({len(response)} chars)")
        return response
    except Exception as e:
        logging.error(f"Error calling LLaMA Grok API: {e}")
        return None


def generate_summary_llama(
    text: str, 
    mode: str = "balanced", 
    lang: str = "en"
) -> Optional[Dict[str, str]]:
    """
    Génère un résumé et un titre accrocheur via LLaMA Grok API.
    """
    mode_config = {
        "short": {"words": "100-150", "style": "concis et direct"},
        "balanced": {"words": "200-300", "style": "équilibré avec tous les points clés"},
        "detailed": {"words": "400-500", "style": "détaillé et complet"}
    }
    config = mode_config.get(mode, mode_config["balanced"])
    
    if lang.startswith("fr"):
        prompt = f"""
Tu es un journaliste expert. Analyse cet article et génère :
TITRE (max 12 mots) et RÉSUMÉ ({config['words']} mots) en style {config['style']}.

Article:
{text[:4500]}
Réponds STRICTEMENT avec ce format :
TITRE: [titre ici]
RÉSUMÉ:
[Résumé ici]
"""
    else:
        prompt = f"""
You are an expert journalist. Analyze this news article and generate:
TITLE (max 12 words) and SUMMARY ({config['words']} words) in style {config['style']}.

Article:
{text[:4500]}
STRICT RESPONSE FORMAT:
TITLE: [your title here]
SUMMARY:
[your summary here]
"""
    response = call_llama_grok(prompt)
    if not response:
        logging.error("LLaMA failed to generate response")
        return None

    # Parsing
    try:
        title_match = re.search(r"TITLE[:\s]+(.+?)(?:\n\n|\nSUMMARY|$)", response, re.IGNORECASE | re.DOTALL)
        summary_match = re.search(r"SUMMARY[:\s]+(.+)$", response, re.IGNORECASE | re.DOTALL)

        title = title_match.group(1).strip() if title_match else "Article Summary"
        summary = summary_match.group(1).strip() if summary_match else None

        if not summary or len(summary.split()) < 20:
            logging.error("Generated summary too short or empty")
            return None

        logging.info(f"Generated title ({len(title)} chars) and summary ({len(summary.split())} words)")
        return {"title": title, "summary": summary}

    except Exception as e:
        logging.error(f"Error parsing LLaMA response: {e}")
        return None


def generate_title_only(text: str, lang: str = "en") -> Optional[str]:
    """
    Génère uniquement un titre accrocheur via LLaMA Grok API.
    """
    if lang.startswith("fr"):
        prompt = f"Article:\n{text[:2000]}\n\nGénère UN TITRE accrocheur (max 12 mots) et répond uniquement avec le titre."
    else:
        prompt = f"Article:\n{text[:2000]}\n\nGenerate ONE catchy title (max 12 words) and reply only with the title."
    
    response = call_llama_grok(prompt, max_tokens=50)
    if response:
        title = response.strip().split("\n")[0]
        return re.sub(r'^["\'"«»]+|["\'"«»]+$', '', title).strip()
    return None
