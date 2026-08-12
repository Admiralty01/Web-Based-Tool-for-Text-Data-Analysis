import logging
import re
from typing import Any, Dict, List, Union
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
import gensim
from gensim import corpora
from sentence_transformers import SentenceTransformer
from nltk.sentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)


class RepresentationGenerator:
    def __init__(self, random_seed: int = 42):
        self.random_seed = random_seed

    def split_into_sentences(self, text: str) -> List[str]:
        """Split a text block into sentences using NLTK or fallback regex."""
        try:
            from nltk.tokenize import sent_tokenize
            sentences = sent_tokenize(text)
        except Exception as e:
            logger.warning(f"NLTK sent_tokenize failed: {e}. Falling back to regex splitting.")
            sentences = [s.strip() for s in re.split(r"[.!?]\s+", text) if s.strip()]
        
        # Filter out extremely short sentences
        return [s for s in sentences if len(s.split()) >= 3]

    def generate_sparse_tfidf(
        self, 
        sentences: List[str], 
        ngram_range: tuple = (1, 2), 
        max_features: int = 100
    ) -> Dict[str, Any]:
        """Generate TF-IDF scores for words and n-grams in the text."""
        if not sentences:
            return {"tfidf_terms": [], "vocabulary_size": 0}
            
        vectorizer = TfidfVectorizer(ngram_range=ngram_range, max_features=max_features)
        try:
            tfidf_matrix = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            mean_scores = tfidf_matrix.mean(axis=0).A1
            
            terms_scores = [
                {"term": name, "score": float(score)} 
                for name, score in zip(feature_names, mean_scores)
            ]
            # Sort terms descending by score
            terms_scores.sort(key=lambda x: x["score"], reverse=True)
            
            return {
                "tfidf_terms": terms_scores,
                "vocabulary_size": len(vectorizer.vocabulary_),
            }
        except ValueError:
            # Handle cases where all vocabulary is filtered out
            return {"tfidf_terms": [], "vocabulary_size": 0}

    def generate_lda_topics(self, tokenized_sentences: List[List[str]], num_topics: int = 5) -> Dict[str, Any]:
        """Run Gensim LDA topic modeling on a sentence-tokenized corpus."""
        valid_sentences = [tokens for tokens in tokenized_sentences if len(tokens) > 0]
        if not valid_sentences:
            return {"topics": [], "message": "No tokens available for topic modeling"}
            
        # Build dictionary and corpus
        dictionary = corpora.Dictionary(valid_sentences)
        corpus = [dictionary.doc2bow(tokens) for tokens in valid_sentences]
        
        try:
            lda_model = gensim.models.LdaModel(
                corpus=corpus,
                id2word=dictionary,
                num_topics=num_topics,
                random_state=self.random_seed,
                passes=5,
                iterations=50
            )
            
            topics = []
            for topic_id in range(num_topics):
                terms = lda_model.show_topic(topic_id, topn=10)
                topics.append({
                    "topic_id": topic_id,
                    "terms": [{"term": term, "weight": float(weight)} for term, weight in terms]
                })
            return {"topics": topics}
        except Exception as e:
            logger.error(f"Gensim LDA training failed: {e}")
            return {"topics": [], "error": str(e)}

    def generate_dense_embeddings(self, texts: Union[str, List[str]], dims: int = 384) -> List[List[float]]:
        """Generate dense embeddings utilizing Sentence-BERT (all-MiniLM-L6-v2).
        
        Includes a robust fallback that produces deterministic unit-length vector arrays
        using a random seed base if HuggingFace servers are unreachable or the host environment lacks internet.
        """
        input_list = [texts] if isinstance(texts, str) else texts
        try:
            # Load Sentence-BERT
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(input_list)
            return embeddings.tolist()
        except Exception as e:
            logger.warning(
                f"SentenceTransformer embedding model load/execution failed: {e}. "
                f"Running fallback deterministic pseudo-embeddings (dims={dims})."
            )
            # Deterministic fallback vectors
            fallback_list = []
            for i, text in enumerate(input_list):
                # Unique seed per string to make it deterministic
                seed_val = abs(hash(text)) % 999999 + self.random_seed
                rng = np.random.default_rng(seed_val)
                vec = rng.uniform(-1.0, 1.0, dims)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                fallback_list.append(vec.tolist())
            return fallback_list
            
    def generate_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze text using NLTK's SentimentIntensityAnalyzer (VADER)."""
        try:
            sia = SentimentIntensityAnalyzer()
            scores = sia.polarity_scores(text)
            pos_pct = round(scores["pos"] * 100)
            neg_pct = round(scores["neg"] * 100)
            neu_pct = 100 - (pos_pct + neg_pct)
            return {
                "score": round(scores["compound"], 2),
                "positive_pct": pos_pct,
                "neutral_pct": neu_pct,
                "negative_pct": neg_pct,
            }
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}. Executing neutral fallback.")
            return {
                "score": 0.0,
                "positive_pct": 0,
                "neutral_pct": 100,
                "negative_pct": 0,
            }

    def compute_all_representations(
        self,
        raw_text: str,
        clean_tokens: List[str],
        lda_topics: int = 5,
        ngram_range: tuple = (1, 2),
        generate_dense: bool = True
    ) -> Dict[str, Any]:
        """Compute the sparse, probabilistic, and dense representations in parallel for a given document."""
        # 1. Sparse TF-IDF (break document into sentences so we have a corpus structure)
        sentences = self.split_into_sentences(raw_text)
        sparse_res = self.generate_sparse_tfidf(sentences, ngram_range=ngram_range)
        
        # 2. LDA Topic Modeling
        # For topic modeling, we token-split each sentence using a quick whitespace tokenizer
        # (since raw_text was preprocessed, we can split sentences on word boundaries)
        tokenized_sentences = []
        for s in sentences:
            # Quick split by spaces, lowering
            words = [w.lower() for w in re.findall(r"\b\w+\b", s) if len(w) > 1]
            tokenized_sentences.append(words)
            
        lda_res = self.generate_lda_topics(tokenized_sentences, num_topics=lda_topics)
        
        # 3. Dense Embedding (Document level)
        # We index the document-level embedding in Elasticsearch
        dense_res = []
        if generate_dense:
            dense_res = self.generate_dense_embeddings(raw_text)
            
        # 4. Sentiment Analysis
        sentiment_res = self.generate_sentiment(raw_text)
            
        return {
            "sparse_tfidf": sparse_res,
            "lda_topics": lda_res,
            "doc_embedding": dense_res[0] if dense_res else [],
            "sentiment": sentiment_res
        }
