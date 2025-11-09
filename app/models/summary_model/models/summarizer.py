from transformers import pipeline
import spacy
from nltk.tokenize import sent_tokenize
import re
import logging
from langdetect import detect, DetectorFactory
from pymongo import MongoClient
from datetime import datetime
from sentence_transformers import SentenceTransformer, util
import numpy as np
from typing import Dict, List, Optional
import torch

# Ensure consistent language detection
DetectorFactory.seed = 0

# ================= CONFIGURATION =================
logging.basicConfig(
    filename="summarizer.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Models with error handling
try:
    device = 0 if torch.cuda.is_available() else -1
    summarizer_model = pipeline("summarization", model="facebook/bart-large-cnn", device=device)
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    logging.info(f"Models loaded successfully on device: {'GPU' if device == 0 else 'CPU'}")
except Exception as e:
    logging.error(f"Failed to load models: {e}")
    raise

# MongoDB with connection pooling
try:
    client = MongoClient(
        "mongodb://localhost:27017/",
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50
    )
    db = client["news_db"]
    collection = db["summaries"]
    # Test connection
    client.server_info()
    logging.info("MongoDB connection established")
except Exception as e:
    logging.warning(f"MongoDB connection failed: {e}")
    collection = None

# ================= CONSTANTS =================
DEFAULT_MAX_CHUNK_WORDS = 300
COMPRESSION_RATIO = 0.25
MAX_SUMMARY_WORDS = 300
MIN_TEXT_LENGTH = 50
SEMANTIC_SIMILARITY_THRESHOLD = 0.85

# ================= UTILITIES =================
def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"\S+@\S+", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    text = re.sub(r"([.,!?;:])\s*([.,!?;:])+", r"\1", text)
    return text.strip()


def remove_boilerplate(text: str) -> str:
    """Remove common boilerplate patterns from articles."""
    patterns = [
        r"(subscribe|sign up|newsletter|cookie policy|privacy policy|terms of service).*?(\.|$)",
        r"(share on|follow us|contact us|related articles|recommended|read more).*?(\.|$)",
        r"(copyright|all rights reserved|©|\(c\)).*?(\.|$)",
        r"(click here|learn more|find out|download|register).*?(\.|$)",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text


def normalize_structure(text: str) -> str:
    """Normalize lists and tables into prose."""
    text = re.sub(r"\n[-*•]\s+", ". ", text)
    text = re.sub(r"\n\d+\.\s+", ". ", text)
    lines = text.split("\n")
    normalized = []
    for line in lines:
        if "|" in line and line.count("|") > 2:
            cols = [c.strip() for c in line.split("|") if c.strip() and not re.match(r"^[-:]+$", c.strip())]
            if cols:
                normalized.append(", ".join(cols) + ".")
        else:
            normalized.append(line)
    return " ".join(normalized)


def chunk_text(text: str, max_words: int = DEFAULT_MAX_CHUNK_WORDS) -> List[str]:
    """Split text into semantically coherent chunks."""
    sentences = sent_tokenize(text)
    chunks = []
    current_chunk = []
    current_words = 0

    for sent in sentences:
        sent_words = len(sent.split())
        if sent_words > max_words:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk, current_words = [], 0
            sub_parts = re.split(r"[,;]", sent)
            temp_chunk = ""
            for part in sub_parts:
                part_with_punct = part + ", "
                if len((temp_chunk + part_with_punct).split()) <= max_words:
                    temp_chunk += part_with_punct
                else:
                    if temp_chunk:
                        chunks.append(temp_chunk.strip().rstrip(","))
                    temp_chunk = part + ", "
            if temp_chunk:
                chunks.append(temp_chunk.strip().rstrip(","))
        elif current_words + sent_words <= max_words:
            current_chunk.append(sent)
            current_words += sent_words
        else:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [sent]
            current_words = sent_words

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    valid_chunks = [c for c in chunks if len(c.split()) >= 20]
    logging.info(f"Created {len(valid_chunks)} chunks from text")
    return valid_chunks


def load_spacy_model(lang: str) -> spacy.language.Language:
    """Load appropriate spaCy model for language."""
    model_map = {
        "fr": "fr_core_news_sm",
        "en": "en_core_web_sm",
        "es": "es_core_news_sm",
        "de": "de_core_news_sm",
    }
    try:
        model_name = model_map.get(lang[:2], "en_core_web_sm")
        return spacy.load(model_name)
    except OSError:
        logging.warning(f"Model {model_name} not found, falling back to en_core_web_sm")
        return spacy.load("en_core_web_sm")


def extract_entities(text: str, nlp_model: spacy.language.Language) -> Dict[str, List[str]]:
    """Extract named entities with improved filtering."""
    doc = nlp_model(text[:100000])
    entities = { "PERSON": [], "ORG": [], "GPE": [], "DATE": [], "MONEY": [], "EVENT": [], "PRODUCT": [] }
    seen = set()
    for ent in doc.ents:
        if len(ent.text) < 2 or ent.text.lower() in ["the", "a", "an", "this", "that"] or ent.text.isdigit():
            continue
        normalized = ent.text.strip()
        if normalized not in seen and ent.label_ in entities:
            entities[ent.label_].append(normalized)
            seen.add(normalized)
    for key in entities:
        entities[key] = entities[key][:10]
    return entities


def extract_quotes(text: str, nlp_model: spacy.language.Language) -> List[str]:
    """Extract quotes with multiple detection strategies."""
    quotes = []
    
    # Strategy 1: Direct quotes with quotation marks (expanded length range)
    quote_patterns = [
        r'"([^"]{15,200})"',
        r'«([^»]{15,200})»',
        r'"([^"]{15,200})"',
        r"'([^']{15,200})'"
    ]
    
    for pattern in quote_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            # Clean and validate
            cleaned = match.strip()
            if len(cleaned.split()) >= 5:  # At least 5 words
                quotes.append(cleaned)
    
    # Strategy 2: Sentences with attribution verbs containing quotes
    dialogue_verbs = [
        "said", "stated", "explained", "mentioned", "added", "noted",
        "argued", "claimed", "wrote", "reported", "announced", "declared",
        "told", "asked", "replied", "responded"
    ]
    
    sentences = sent_tokenize(text)
    for sent in sentences:
        # Must contain quotation marks AND attribution verb
        if '"' in sent or '"' in sent or '"' in sent:
            sent_lower = sent.lower()
            if any(verb in sent_lower for verb in dialogue_verbs):
                if 15 <= len(sent) <= 200:
                    quotes.append(sent.strip())
    
    # Strategy 3: "According to X" patterns
    attribution_patterns = [
        r'According to [^,]+, ["\"]([^"\"]+)["\"]',
        r'According to [^,]+, ([^.!?]{20,150})[.!?]',
        r'[A-Z][a-z]+ (said|stated|explained|noted), ["\"]([^"\"]+)["\"]'
    ]
    
    for pattern in attribution_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Handle tuple results from regex groups
            quote_text = match if isinstance(match, str) else match[-1]
            if len(quote_text.split()) >= 5:
                quotes.append(quote_text.strip())
    
    # Deduplicate while preserving order
    seen = set()
    unique_quotes = []
    for quote in quotes:
        # Normalize for comparison
        normalized = quote.lower().strip()
        if normalized not in seen and len(quote.split()) >= 5:
            seen.add(normalized)
            unique_quotes.append(quote)
    
    # Sort by informativeness (balance length and position)
    unique_quotes.sort(key=lambda x: len(x.split()), reverse=True)
    
    return unique_quotes[:5]

def remove_duplicates_semantic(text: str, threshold: float = SEMANTIC_SIMILARITY_THRESHOLD) -> str:
    """Remove semantically duplicate sentences using embeddings."""
    sentences = sent_tokenize(text)
    
    if len(sentences) <= 1:
        return text
    
    try:
        embeddings = embedding_model.encode(sentences, convert_to_tensor=True)
        keep_indices = []
        
        for i in range(len(sentences)):
            is_unique = True
            for j in keep_indices:
                similarity = util.pytorch_cos_sim(embeddings[i], embeddings[j]).item()
                if similarity >= threshold:
                    is_unique = False
                    break
            
            if is_unique:
                keep_indices.append(i)
        
        result = " ".join([sentences[i] for i in keep_indices])
        logging.info(f"Removed {len(sentences) - len(keep_indices)} duplicate sentences")
        
        return result
        
    except Exception as e:
        logging.error(f"Error in semantic deduplication: {e}")
        return text

def generate_title(text: str, summary: str, nlp_model: spacy.language.Language) -> str:
    """Generate an informative title using multiple strategies."""
    
    # Strategy 1: Extract main subject and action from summary
    try:
        doc = nlp_model(summary[:300])
        
        # Find main entities with high importance
        main_entities = []
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG", "PRODUCT", "EVENT"] and len(ent.text) > 2:
                main_entities.append(ent.text)
                if len(main_entities) >= 2:
                    break
        
        # Find meaningful verbs (exclude common ones)
        excluded_verbs = {"is", "are", "was", "were", "be", "been", "have", "has", "had", "will", "would", "could", "should"}
        meaningful_verbs = []
        
        for token in doc:
            if (token.pos_ == "VERB" and 
                token.lemma_.lower() not in excluded_verbs and
                not token.is_stop and
                len(token.text) > 3):
                meaningful_verbs.append(token.lemma_)
                if len(meaningful_verbs) >= 1:
                    break
        
        # Construct title
        if main_entities and meaningful_verbs:
            if len(main_entities) >= 2:
                title = f"{main_entities[0]} and {main_entities[1]}: {meaningful_verbs[0].capitalize()}s"
            else:
                title = f"{main_entities[0]} {meaningful_verbs[0].capitalize()}s"
            
            # Validate length
            if 3 <= len(title.split()) <= 10:
                return title
        
    except Exception as e:
        logging.warning(f"Title strategy 1 failed: {e}")
    
    # Strategy 2: Extract informative noun phrases
    try:
        doc = nlp_model(summary[:300])
        
        # Get noun chunks that look like titles
        title_candidates = []
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.strip()
            word_count = len(chunk_text.split())
            
            # Good title length and not starting with determiners
            if (4 <= word_count <= 10 and 
                not chunk_text.lower().startswith(('the ', 'a ', 'an '))):
                title_candidates.append(chunk_text)
        
        if title_candidates:
            # Return first good candidate
            return title_candidates[0].capitalize()
            
    except Exception as e:
        logging.warning(f"Title strategy 2 failed: {e}")
    
    # Strategy 3: Use first sentence if it's concise
    try:
        sentences = sent_tokenize(summary)
        if sentences:
            first_sent = sentences[0]
            words = first_sent.split()
            
            # If short enough, use as-is
            if 5 <= len(words) <= 12:
                return first_sent.rstrip(".!?")
            
            # Otherwise, extract subject-verb-object
            doc = nlp_model(first_sent)
            subjects = [t.text for t in doc if t.dep_ in ["nsubj", "nsubjpass"]]
            verbs = [t.text for t in doc if t.pos_ == "VERB"]
            objects = [t.text for t in doc if t.dep_ in ["dobj", "attr"]]
            
            if subjects and verbs:
                parts = [subjects[0]]
                parts.append(verbs[0])
                if objects:
                    parts.append(objects[0])
                
                title = " ".join(parts)
                if 3 <= len(title.split()) <= 10:
                    return title.capitalize()
            
            # Last resort: truncate
            return " ".join(words[:10])
            
    except Exception as e:
        logging.warning(f"Title strategy 3 failed: {e}")
    
    # Ultimate fallback
    return "News Summary"

def extract_date(text: str) -> str:
    """Extract publication date with multiple patterns."""
    # First 2000 characters are most likely to contain the date
    search_text = text[:2000]
    
    date_patterns = [
        # ISO format: 2025-10-14
        (r"\b(\d{4}-\d{2}-\d{2})\b", "%Y-%m-%d"),
        # Format: 14 October 2025
        (r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b", "%d %B %Y"),
        # Format: October 14, 2025
        (r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})\b", "%B %d, %Y"),
        # Format: Oct 14, 2025
        (r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})\b", "%b %d, %Y"),
        # Format: 10/14/2025
        (r"\b(\d{1,2}/\d{1,2}/\d{4})\b", "%m/%d/%Y"),
        # Format: 14.10.2025
        (r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b", "%d.%m.%Y"),
    ]
    
    for pattern, date_format in date_patterns:
        match = re.search(pattern, search_text, re.IGNORECASE)
        if match:
            try:
                date_str = match.group(1)
                parsed_date = datetime.strptime(date_str, date_format)
                
                # Validate date is reasonable (not in far future)
                if parsed_date.year <= datetime.now().year + 1:
                    return parsed_date.strftime("%B %d, %Y")
            except ValueError:
                continue
    
    # If no date found, return "Not specified"
    logging.info("No publication date found in text")
    return "Not specified"

def extract_numbers_events(text: str) -> Dict[str, List[str]]:
    """Extract significant numbers and events."""
    # Extract numbers with context (percentages, money, large numbers)
    numbers = []
    number_patterns = [
        r"\b\d+(?:[.,]\d+)?(?:\s*(?:million|billion|thousand|trillion))?\b",
        r"\b\d+(?:[.,]\d+)?\s*(?:percent|%)\b",
        r"\$\s*\d+(?:[.,]\d+)?(?:\s*(?:million|billion|thousand))?\b"
    ]
    
    for pattern in number_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        numbers.extend(matches)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_numbers = []
    for num in numbers:
        num_clean = num.strip()
        if num_clean not in seen:
            seen.add(num_clean)
            unique_numbers.append(num_clean)
    
    # Extract event keywords with context
    event_keywords = [
        "election", "meeting", "conference", "summit", "crisis", "protest",
        "award", "launch", "attack", "strike", "deal", "agreement",
        "announcement", "resignation", "appointment", "merger", "acquisition",
        "scandal", "trial", "verdict", "ceremony", "celebration"
    ]
    
    events = []
    text_lower = text.lower()
    
    for keyword in event_keywords:
        if re.search(r"\b" + keyword + r"\b", text_lower):
            events.append(keyword)
    
    return {
        "numbers": unique_numbers[:10],
        "events": list(set(events))[:5]
    }

def extract_5w1h(summary: str, nlp_model: spacy.language.Language) -> Dict[str, List[str]]:
    """Extract 5W1H structure with improved categorization."""
    sentences = sent_tokenize(summary)
    
    structure = {
        "Who": [],
        "What": [],
        "When": [],
        "Where": [],
        "Why": [],
        "How": []
    }
    
    # Keywords for each category
    keywords = {
        "Why": ["because", "due to", "reason", "caused by", "since", "as a result", 
                "therefore", "consequently", "as", "for", "to"],
        "How": ["by", "through", "method", "process", "way", "manner", "using", 
                "with", "via", "means", "approach"],
        "When": ["when", "after", "before", "during", "while", "since", "until", 
                 "on", "in", "at", "recently", "today", "yesterday", "now", "currently"]
    }
    
    for sent in sentences:
        if not sent.strip():
            continue
            
        sent_lower = sent.lower()
        
        try:
            doc = nlp_model(sent)
        except Exception as e:
            logging.warning(f"Error processing sentence for 5W1H: {e}")
            continue
        
        # Calculate scores for each category
        scores = {
            "Who": 0,
            "What": 0,
            "When": 0,
            "Where": 0,
            "Why": 0,
            "How": 0
        }
        
        # Analyze entities
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG"]:
                scores["Who"] += 3
            elif ent.label_ == "GPE":
                scores["Where"] += 3
            elif ent.label_ == "DATE":
                scores["When"] += 4
        
        # Analyze keywords with context
        for category, words in keywords.items():
            for word in words:
                # Count occurrences
                count = sent_lower.count(" " + word + " ") + sent_lower.count(word + " ")
                scores[category] += count * 2
        
        # Boost "What" for sentences with strong verbs and objects
        strong_verbs = [token for token in doc if token.pos_ == "VERB" and not token.is_stop]
        if strong_verbs and len(strong_verbs) >= 2:
            scores["What"] += 2
        
        # If no strong indicators, default to "What"
        if max(scores.values()) == 0:
            scores["What"] = 1
        
        # Assign to best category if not full
        best_category = max(scores, key=scores.get)
        
        # Ensure each category gets at least some representation
        if len(structure[best_category]) < 2 and scores[best_category] > 0:
            structure[best_category].append(sent.strip())
        elif all(len(structure[cat]) >= 2 for cat in structure):
            break
    
    # Fill empty categories with remaining sentences if possible
    remaining_sentences = [s for s in sentences if not any(s in structure[cat] for cat in structure)]
    empty_categories = [cat for cat in structure if len(structure[cat]) == 0]
    
    for i, cat in enumerate(empty_categories):
        if i < len(remaining_sentences):
            structure[cat].append(remaining_sentences[i].strip())
    
    return structure

def evaluate_summary_quality(original: str, summary: str, nlp_model: spacy.language.Language) -> Dict[str, float]:
    """Evaluate summary quality metrics."""
    try:
        # Entity coverage
        orig_doc = nlp_model(original[:5000])
        summ_doc = nlp_model(summary)
        
        orig_entities = set([ent.text.lower() for ent in orig_doc.ents if len(ent.text) > 2])
        summ_entities = set([ent.text.lower() for ent in summ_doc.ents if len(ent.text) > 2])
        
        entity_coverage = (len(orig_entities & summ_entities) / len(orig_entities) 
                          if orig_entities else 0)
        
        # Semantic coherence
        orig_embedding = embedding_model.encode(original[:2000])
        summ_embedding = embedding_model.encode(summary)
        coherence = float(util.cos_sim(orig_embedding, summ_embedding).item())
        
        # Compression quality
        orig_words = len(original.split())
        summ_words = len(summary.split())
        compression_ratio = summ_words / orig_words if orig_words > 0 else 0
        
        return {
            "entity_coverage": round(entity_coverage, 2),
            "semantic_coherence": round(coherence, 2),
            "compression_ratio": round(compression_ratio, 3)
        }
        
    except Exception as e:
        logging.error(f"Quality evaluation failed: {e}")
        return {"entity_coverage": 0.0, "semantic_coherence": 0.0, "compression_ratio": 0.0}

# ================= MAIN FUNCTION =================
def summarize(
    text: str,
    mode: str = "balanced",
    save_to_db: bool = False,
    include_quality_metrics: bool = False
) -> Optional[Dict]:
    """
    Summarize text with comprehensive analysis.
    
    Args:
        text: Input text to summarize
        mode: Summarization mode ('short', 'balanced', 'detailed')
        save_to_db: Whether to save results to MongoDB
        include_quality_metrics: Whether to compute quality metrics
    
    Returns:
        Dictionary with summary and analysis, or None on failure
    """
    start_time = datetime.now()
    
    try:
        # ===== PREPROCESSING =====
        logging.info("Starting summarization process")
        
        text = clean_text(text)
        text = remove_boilerplate(text)
        text = normalize_structure(text)
        
        if not text or len(text.split()) < MIN_TEXT_LENGTH:
            logging.warning(f"Text too short: {len(text.split()) if text else 0} words")
            return None
        
        # Language detection
        try:
            lang = detect(text)
        except Exception as e:
            logging.warning(f"Language detection failed: {e}, defaulting to English")
            lang = "en"
        
        nlp_model = load_spacy_model(lang)
        original_words = len(text.split())
        target_length = min(MAX_SUMMARY_WORDS, int(original_words * COMPRESSION_RATIO))
        
        logging.info(f"Processing {original_words} words in {lang}")
        
        # ===== MODE CONFIGURATION =====
        mode_params = {
            "short": {"max_length": 130, "min_length": 50},
            "balanced": {"max_length": 200, "min_length": 100},
            "detailed": {"max_length": 350, "min_length": 150}
        }
        params = mode_params.get(mode, mode_params["balanced"])
        
        # ===== CHUNKING & SUMMARIZATION =====
        chunks = chunk_text(text)
        
        if not chunks:
            logging.warning("No valid chunks created")
            return None
        
        chunk_summaries = []
        
        for i, chunk in enumerate(chunks):
            chunk_word_count = len(chunk.split())
            
            # Skip summarization for very short chunks
            if chunk_word_count < 50:
                chunk_summaries.append(chunk)
                logging.info(f"Chunk {i+1}/{len(chunks)}: Too short, using original")
                continue
            
            # Adjust parameters for short chunks
            chunk_max = min(params["max_length"], int(chunk_word_count * 0.7))
            chunk_min = min(params["min_length"], int(chunk_word_count * 0.3))
            
            # Ensure min < max
            if chunk_min >= chunk_max:
                chunk_min = max(30, chunk_max - 20)
            
            try:
                result = summarizer_model(
                    chunk,
                    max_length=chunk_max,
                    min_length=chunk_min,
                    do_sample=False,
                    truncation=True
                )
                chunk_summaries.append(result[0]["summary_text"])
                logging.info(f"Chunk {i+1}/{len(chunks)}: Summarized ({chunk_word_count} → {len(result[0]['summary_text'].split())} words)")
                
            except (RuntimeError, ValueError, IndexError) as e:
                logging.warning(f"Chunk {i+1} summarization failed: {e}")
                # Use beginning of chunk as fallback
                fallback = " ".join(chunk.split()[:100])
                chunk_summaries.append(fallback)
                logging.info(f"Chunk {i+1}/{len(chunks)}: Using fallback")
        
        if not chunk_summaries:
            logging.error("No chunk summaries generated")
            return None
        
        combined_summary = " ".join(chunk_summaries)
        
        # ===== ITERATIVE REFINEMENT =====
        iteration = 0
        max_iterations = 3
        current_length = len(combined_summary.split())
        
        while (current_length > target_length * 1.5 and iteration < max_iterations):
            try:
                # Adjust parameters based on current length
                refine_max = min(params["max_length"], int(current_length * 0.7))
                refine_min = min(params["min_length"], int(current_length * 0.4))
                
                # Ensure min < max
                if refine_min >= refine_max:
                    refine_min = max(50, refine_max - 30)
                
                result = summarizer_model(
                    combined_summary,
                    max_length=refine_max,
                    min_length=refine_min,
                    do_sample=False,
                    truncation=True
                )
                combined_summary = result[0]["summary_text"]
                current_length = len(combined_summary.split())
                logging.info(f"Refinement iteration {iteration + 1}: {current_length} words")
                
            except Exception as e:
                logging.warning(f"Refinement iteration {iteration + 1} failed: {e}")
                break
            
            iteration += 1
        
        # ===== DEDUPLICATION =====
        combined_summary = remove_duplicates_semantic(combined_summary)
        
        # ===== INFORMATION EXTRACTION =====
        logging.info("Extracting metadata and entities")
        
        quotes = extract_quotes(text, nlp_model)
        entities = extract_entities(text, nlp_model)
        numbers_events = extract_numbers_events(text)
        date_pub = extract_date(text)
        structure_5w1h = extract_5w1h(combined_summary, nlp_model)
        title = generate_title(text, combined_summary, nlp_model)
        
        # ===== BUILD RESULT =====
        result = {
            "title": title,
            "summary": combined_summary,
            "structure_5w1h": structure_5w1h,
            "key_quotes": quotes,
            "entities": entities,
            "numbers_events": numbers_events,
            "date_published": date_pub,
            "metadata": {
                "language": lang,
                "original_length": original_words,
                "summary_length": len(combined_summary.split()),
                "compression_ratio": round(len(combined_summary.split()) / original_words, 3),
                "processing_time": round((datetime.now() - start_time).total_seconds(), 2),
                "mode": mode,
                "chunks_processed": len(chunks)
            }
        }
        
        # ===== QUALITY METRICS (OPTIONAL) =====
        if include_quality_metrics:
            quality = evaluate_summary_quality(text, combined_summary, nlp_model)
            result["quality_metrics"] = quality
            logging.info(f"Quality metrics: {quality}")
        
        # ===== SAVE TO DATABASE =====
        if save_to_db and collection is not None:
            try:
                result_copy = result.copy()
                result_copy["created_at"] = datetime.now()
                collection.insert_one(result_copy)
                logging.info("Summary saved to MongoDB")
            except Exception as e:
                logging.error(f"Failed to save to MongoDB: {e}")
        
        logging.info(f"Summarization completed in {result['metadata']['processing_time']}s")
        return result
        
    except Exception as e:
        logging.error(f"Critical error in summarization: {e}", exc_info=True)
        return None

# ================= BATCH PROCESSING =================
def summarize_batch(
    texts: List[str],
    mode: str = "balanced",
    save_to_db: bool = False
) -> List[Optional[Dict]]:
    """Process multiple texts in batch."""
    results = []
    total = len(texts)
    
    logging.info(f"Starting batch processing of {total} documents")
    
    for i, text in enumerate(texts):
        logging.info(f"Processing document {i+1}/{total}")
        
        try:
            result = summarize(text, mode=mode, save_to_db=save_to_db)
            results.append(result)
            
            if result:
                logging.info(f"Document {i+1} processed successfully")
            else:
                logging.warning(f"Document {i+1} failed to process")
                
        except Exception as e:
            logging.error(f"Error processing document {i+1}: {e}")
            results.append(None)
    
    successful = sum(1 for r in results if r is not None)
    logging.info(f"Batch processing complete: {successful}/{total} successful")
    
    return results