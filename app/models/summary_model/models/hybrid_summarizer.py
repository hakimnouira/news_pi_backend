"""
Hybrid Summarizer - Combine intelligemment LLaMA Grok et BART
Pour obtenir le meilleur résumé avec titre accrocheur, date et métadonnées
"""

import logging
from typing import Optional, Dict
from datetime import datetime

# Import des modules
from . import summarizer
from . import llama_summarizer as llama
from ..db_storage import SummaryStorageManager
from ..evaluation_module import SummarizerEvaluator

# Configuration du logging
logging.basicConfig(
    filename="hybrid_summarizer.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ✅ FONCTION PRINCIPALE QUE LE SCHEDULER UTILISE
def summarize_bart_llama_title(
    text: str,
    mode: str = "balanced",
    save_to_db: bool = False,
    include_quality_metrics: bool = False
) -> Optional[Dict]:
    """
    Résumé hybride OPTIMAL : Titre par LLaMA + Résumé par BART
    C'EST LA MEILLEURE COMBINAISON !
    """
    return summarize_hybrid(
        text=text,
        mode=mode,
        save_to_db=save_to_db,
        include_quality_metrics=include_quality_metrics,
        prefer_llama_title=True
    )

# ✅ FONCTION ALTERNATIVE (TOUT PAR LLAMA)
def summarize_full_llama(
    text: str,
    mode: str = "balanced",
    save_to_db: bool = False,
    include_quality_metrics: bool = False
) -> Optional[Dict]:
    """
    Version alternative : Utilise LLaMA pour TOUT (titre + résumé)
    """
    return summarize_with_llama_summary(
        text=text,
        mode=mode,
        save_to_db=save_to_db,
        include_quality_metrics=include_quality_metrics
    )

def summarize_hybrid(
    text: str,
    mode: str = "balanced",
    save_to_db: bool = False,
    include_quality_metrics: bool = False,
    prefer_llama_title: bool = True
) -> Optional[Dict]:
    """
    Résumé hybride intelligent : combine LLaMA (titres) et BART (résumé + analyse).
    """
    start_time = datetime.now()
    storage = SummaryStorageManager() if save_to_db else None
    evaluator = SummarizerEvaluator() if include_quality_metrics else None
    
    logging.info("="*60)
    logging.info("STARTING HYBRID SUMMARIZATION")
    logging.info("="*60)
    
    try:
        # ===== ÉTAPE 1: BART SUMMARIZATION (TOUJOURS) =====
        logging.info("Step 1: Running BART summarization (base analysis)...")
        
        bart_result = summarizer.summarize(
            text=text,
            mode=mode,
            save_to_db=False,
            include_quality_metrics=include_quality_metrics
        )
        
        if not bart_result:
            logging.error("BART summarization failed completely")
            return None
        
        logging.info(f"✓ BART completed: {bart_result['metadata']['summary_length']} words")
        
        # ===== ÉTAPE 2: LLaMA TITLE GENERATION (OPTIONNEL) =====
        llama_title = None
        if prefer_llama_title:
            logging.info("Step 2: Attempting LLaMA title generation...")
            try:
                lang = bart_result['metadata'].get('language', 'en')
                llama_title = llama.generate_title_only(text=text, lang=lang)
                
                if llama_title and len(llama_title) > 5:
                    logging.info(f"✓ LLaMA title generated: '{llama_title[:50]}...'")
                else:
                    logging.warning("✗ LLaMA title invalid or too short")
                    llama_title = None
            except Exception as e:
                logging.warning(f"✗ LLaMA title generation failed: {e}")
                llama_title = None
        else:
            logging.info("Step 2: Skipping LLaMA title (prefer_llama_title=False)")
        
        # ===== ÉTAPE 3: ASSEMBLAGE HYBRIDE =====
        final_title = llama_title if llama_title and prefer_llama_title else bart_result['title']
        title_source = "llama" if final_title == llama_title else "bart"
        
        hybrid_result = {
            "title": final_title,
            "summary": bart_result['summary'],
            "date_published": bart_result['date_published'],
            "structure_5w1h": bart_result['structure_5w1h'],
            "key_quotes": bart_result['key_quotes'],
            "entities": bart_result['entities'],
            "numbers_events": bart_result['numbers_events'],
            "metadata": {
                **bart_result['metadata'],
                "title_source": title_source,
                "method": "hybrid",
                "processing_time": round((datetime.now() - start_time).total_seconds(), 2)
            }
        }
        
        # ===== ÉVALUATION (OPTIONNEL) =====
        evaluation_metrics = None
        if include_quality_metrics and evaluator:
            evaluation_metrics = evaluator.evaluate_single_summary(text, hybrid_result, "hybrid")
            hybrid_result['metadata']['evaluation_metrics'] = evaluation_metrics
        
        # ===== SAUVEGARDE EN BASE (OPTIONNEL) =====
        if save_to_db and storage:
            try:
                storage_result = storage.save_article_with_summary(text, hybrid_result, "hybrid", evaluation_metrics)
                logging.info(f"✓ Saved to MongoDB: {storage_result}")
            except Exception as e:
                logging.error(f"✗ MongoDB save failed: {e}")
        
        total_time = hybrid_result['metadata']['processing_time']
        logging.info("="*60)
        logging.info(f"HYBRID SUMMARIZATION COMPLETED in {total_time}s")
        logging.info(f"  - Title: {final_title[:50]}...")
        logging.info(f"  - Summary: {len(hybrid_result['summary'].split())} words")
        logging.info(f"  - Date: {hybrid_result['date_published']}")
        logging.info(f"  - Entities: {sum(len(v) for v in hybrid_result['entities'].values())} found")
        logging.info(f"  - Quotes: {len(hybrid_result['key_quotes'])} extracted")
        logging.info("="*60)
        
        if storage:
            storage.close()
        
        return hybrid_result
        
    except Exception as e:
        logging.error(f"Critical error in hybrid summarization: {e}", exc_info=True)
        return None
    finally:
        if storage:
            storage.close()

def summarize_with_llama_summary(
    text: str,
    mode: str = "balanced",
    save_to_db: bool = False,
    include_quality_metrics: bool = False
) -> Optional[Dict]:
    """
    Version alternative : Utilise LLaMA pour TOUT (titre + résumé),
    mais conserve les extractions d'informations de BART.
    """
    start_time = datetime.now()
    storage = SummaryStorageManager() if save_to_db else None
    evaluator = SummarizerEvaluator() if include_quality_metrics else None
    
    logging.info("="*60)
    logging.info("STARTING FULL LLaMA SUMMARIZATION (with BART extraction)")
    logging.info("="*60)
    
    try:
        text = summarizer.clean_text(text)
        text = summarizer.remove_boilerplate(text)
        text = summarizer.normalize_structure(text)
        
        if not text or len(text.split()) < summarizer.MIN_TEXT_LENGTH:
            logging.warning(f"Text too short: {len(text.split())} words")
            return None
        
        try:
            from langdetect import detect
            lang = detect(text)
        except:
            lang = "en"
        
        logging.info(f"Processing {len(text.split())} words in {lang}")
        
        llama_result = llama.generate_summary_llama(text=text, mode=mode, lang=lang)
        
        if not llama_result:
            logging.warning("✗ LLaMA failed, falling back to BART...")
            return summarizer.summarize(text=text, mode=mode, save_to_db=False, include_quality_metrics=include_quality_metrics)
        
        logging.info(f"✓ LLaMA completed: {len(llama_result['summary'].split())} words")
        
        nlp_model = summarizer.load_spacy_model(lang)
        quotes = summarizer.extract_quotes(text, nlp_model)
        entities = summarizer.extract_entities(text, nlp_model)
        numbers_events = summarizer.extract_numbers_events(text)
        date_pub = summarizer.extract_date(text)
        structure_5w1h = summarizer.extract_5w1h(llama_result['summary'], nlp_model)
        
        final_result = {
            "title": llama_result['title'],
            "summary": llama_result['summary'],
            "date_published": date_pub,
            "structure_5w1h": structure_5w1h,
            "key_quotes": quotes,
            "entities": entities,
            "numbers_events": numbers_events,
            "metadata": {
                "language": lang,
                "original_length": len(text.split()),
                "summary_length": len(llama_result['summary'].split()),
                "compression_ratio": round(len(llama_result['summary'].split()) / len(text.split()), 3),
                "processing_time": round((datetime.now() - start_time).total_seconds(), 2),
                "mode": mode,
                "method": "llama_full_with_extraction"
            }
        }
        
        # ===== ÉVALUATION (OPTIONNEL) =====
        evaluation_metrics = None
        if include_quality_metrics and evaluator:
            evaluation_metrics = evaluator.evaluate_single_summary(text, final_result, "llama_full")
            final_result['metadata']['evaluation_metrics'] = evaluation_metrics
        
        # ===== SAUVEGARDE EN BASE (OPTIONNEL) =====
        if save_to_db and storage:
            try:
                storage_result = storage.save_article_with_summary(text, final_result, "llama_full", evaluation_metrics)
                logging.info(f"✓ Saved to MongoDB: {storage_result}")
            except Exception as e:
                logging.error(f"✗ MongoDB save failed: {e}")
        
        total_time = final_result['metadata']['processing_time']
        logging.info("="*60)
        logging.info(f"FULL LLaMA SUMMARIZATION COMPLETED in {total_time}s")
        logging.info("="*60)
        
        if storage:
            storage.close()
        
        return final_result
        
    except Exception as e:
        logging.error(f"Critical error: {e}", exc_info=True)
        return None
    finally:
        if storage:
            storage.close()