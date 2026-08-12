import logging
import re
from typing import Dict, Any, List
import nltk
from nltk.corpus import stopwords
import spacy
import langdetect
from langdetect import DetectorFactory

logger = logging.getLogger(__name__)

# Ensure langdetect is deterministic
DetectorFactory.seed = 42


class TextPreprocessor:
    def __init__(self):
        # Load spaCy english model
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            logger.info("spaCy model en_core_web_sm not found, downloading...")
            spacy.cli.download("en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")

        # Load NLTK stopwords
        try:
            self.nltk_stopwords = set(stopwords.words("english"))
        except LookupError:
            logger.info("NLTK stopwords not found, downloading...")
            nltk.download("stopwords")
            self.nltk_stopwords = set(stopwords.words("english"))

    def detect_language(self, text: str) -> str:
        """Detect language of the text sample (first 1000 characters). Defaults to 'en'."""
        if not text.strip():
            return "unknown"
        try:
            # Use a slice for speed and consistency
            sample = text[:1000]
            return langdetect.detect(sample)
        except Exception as e:
            logger.warning(f"Language detection failed: {e}. Defaulting to 'en'.")
            return "en"

    def clean_whitespace(self, text: str) -> str:
        """Standardize spacing and strip text."""
        return re.sub(r"\s+", " ", text).strip()

    def process(self, text: str) -> Dict[str, Any]:
        """Runs the preprocessing steps deterministically.
        
        1. Language detection.
        2. Tokenization and lemmatization via spaCy.
        3. Stop-word and punctuation filtering using both spaCy and NLTK corpora.
        
        Returns a dictionary with raw statistics and cleaned tokens/text.
        """
        language = self.detect_language(text)
        cleaned_whitespace = self.clean_whitespace(text)
        
        # spaCy processing. Disable parsing for speed but keep NER active.
        doc = self.nlp(cleaned_whitespace, disable=["parser"])
        
        # Extract named entities
        entities: List[Dict[str, str]] = []
        seen = set()
        for ent in doc.ents:
            val = (ent.text.strip(), ent.label_)
            if val not in seen and len(ent.text.strip()) > 1:
                seen.add(val)
                entities.append({
                    "text": ent.text.strip(),
                    "label": ent.label_
                })
        
        clean_tokens: List[str] = []
        for token in doc:
            # Exclude punctuation, spaces, numbers, and symbols
            if token.is_punct or token.is_space or token.like_num or token.pos_ in ["PUNCT", "SPACE", "NUM", "SYM"]:
                continue
                
            # Keep lowercase lemma
            lemma = token.lemma_.lower().strip()
            
            # Skip empty entries
            if not lemma:
                continue
                
            # Filter stop-words from both lists
            if token.is_stop or lemma in self.nltk_stopwords:
                continue
                
            # Filter out tokens that are extremely short
            if len(lemma) < 2:
                continue
                
            clean_tokens.append(lemma)

        return {
            "language": language,
            "clean_tokens": clean_tokens,
            "clean_text": " ".join(clean_tokens),
            "char_count": len(text),
            "word_count": len(text.split()),
            "entities": entities
        }
