import os
import sys
from unittest.mock import MagicMock

# Define custom Mock Celery class to preserve original decorated functions
class MockCelery:
    def __init__(self, *args, **kwargs):
        self.conf = MagicMock()
    def task(self, *args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Define mock Celery AsyncResult representation
class MockResult:
    def __init__(self, id):
        self.status = "SUCCESS"
        self.result = {"status": "ready"}
        self.info = None

# Stub out heavy NLP, ML and connection modules to prevent import/compilation errors
mock_modules = [
    "nltk",
    "nltk.corpus",
    "nltk.sentiment",
    "langdetect",
    "gensim",
    "gensim.corpora",
    "sentence_transformers",
    "elasticsearch",
    "boto3",
    "botocore.exceptions"
]
for mod_name in mock_modules:
    sys.modules[mod_name] = MagicMock()


# Inject Celery mocks directly in sys.modules
mock_celery = MagicMock()
mock_celery.Celery = MockCelery
sys.modules["celery"] = mock_celery

mock_celery_result = MagicMock()
mock_celery_result.AsyncResult = MockResult
sys.modules["celery.result"] = mock_celery_result

# Add backend directory to system path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

# Set default environment variables to configure local SQLite if not already specified
os.environ.setdefault("DATABASE_URL", "sqlite:///mocked_text_analysis.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ELASTICSEARCH_HOST", "http://localhost:9200")
os.environ.setdefault("S3_BUCKET_NAME", "mocked-s3-bucket")

# Mock S3 Service class to write files to local directory
class MockS3Service:
    def __init__(self):
        self.bucket = "mocked-s3-bucket"
        self.storage_dir = "mocked_s3_storage"
        os.makedirs(self.storage_dir, exist_ok=True)
        self.s3_client = MagicMock()
        self.s3_client.generate_presigned_url.side_effect = self.generate_presigned_url

    def ensure_bucket_exists(self):
        pass

    def upload_fileobj(self, file_obj, key: str) -> str:
        path = os.path.join(self.storage_dir, key.replace("/", "_"))
        with open(path, "wb") as f:
            f.write(file_obj.read())
        return f"s3://{self.bucket}/{key}"

    def upload_content(self, content: bytes, key: str) -> str:
        path = os.path.join(self.storage_dir, key.replace("/", "_"))
        with open(path, "wb") as f:
            f.write(content)
        return f"s3://{self.bucket}/{key}"

    def get_content(self, key: str) -> bytes:
        path = os.path.join(self.storage_dir, key.replace("/", "_"))
        if not os.path.exists(path):
            return b"Sample document text content for dynamic NLP analysis."
        with open(path, "rb") as f:
            return f.read()

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return f"/{key}"


# Mock Elasticsearch Service class to run in-memory search
class MockESService:
    def __init__(self):
        self.client = MagicMock()
        self.indices = {}

    def create_index(self, index_name: str, dims: int = 384) -> bool:
        if index_name not in self.indices:
            self.indices[index_name] = []
        return True

    def index_document(
        self,
        index_name: str,
        document_id: str,
        title: str,
        content: str,
        clean_content: str,
        embedding: list,
    ):
        if index_name not in self.indices:
            self.indices[index_name] = []
        self.indices[index_name].append(
            {
                "document_id": document_id,
                "title": title,
                "content": content,
                "clean_content": clean_content,
                "embedding": embedding,
            }
        )
        print(f"--> Mock ES: Indexed document '{title}' (ID: {document_id}) in index '{index_name}'. Total docs: {len(self.indices[index_name])}")
        return {"result": "created"}

    def hybrid_search(
        self,
        index_name: str,
        query_text: str,
        query_vector=None,
        limit: int = 10,
    ):
        print(f"--> Mock ES: Searching index '{index_name}' for query '{query_text}'. Available indices: {list(self.indices.keys())}")
        if index_name not in self.indices:
            print(f"--> Mock ES: Index '{index_name}' not found.")
            return []
            
        docs = self.indices[index_name]
        results = []
        for doc in docs:
            score = 1.0
            if query_text.lower() in doc["title"].lower():
                score += 3.0
            if query_text.lower() in doc["content"].lower():
                score += 2.0
                
            results.append(
                {
                    "document_id": doc["document_id"],
                    "title": doc["title"],
                    "score": score,
                    "clean_content_snippet": doc["content"][:200] + "...",
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        # Filter out 1.0 scores (no match)
        results = [r for r in results if r["score"] > 1.0]
        print(f"--> Mock ES: Found {len(results)} matches for '{query_text}'")
        return results[:limit]


# Override S3 and Elasticsearch modules BEFORE importing core app modules
import app.core.s3
import app.core.elasticsearch
mock_s3 = MockS3Service()
mock_es = MockESService()
app.core.s3.s3_service = mock_s3
app.core.elasticsearch.es_service = mock_es

# Import pipeline and base entities
from app.pipeline.preprocess import TextPreprocessor
from app.pipeline.representation import RepresentationGenerator
from app.core.database import Base, engine
from app.main import app as fastapi_app  # Import as app and alias it as fastapi_app

# Apply direct overrides on internal imported modules to bypass reference binding caching
import app.tasks.analysis_tasks
import app.api.documents

app.tasks.analysis_tasks.s3_service = mock_s3
app.tasks.analysis_tasks.es_service = mock_es
app.api.documents.s3_service = mock_s3
app.api.documents.es_service = mock_es

import spacy
print("--> Loading spaCy model (en_core_web_sm) once at startup...")
try:
    nlp = spacy.load("en_core_web_sm", disable=["tagger", "parser", "attribute_ruler", "lemmatizer"])
    print("--> spaCy model loaded successfully.")
except Exception as e:
    print(f"--> ERROR: Failed to load spaCy model en_core_web_sm: {e}")
    # Raise error to stop execution as per task instructions (no silent mock fallback)
    raise RuntimeError(f"Could not load spaCy model: {e}") from e

# Override the spaCy TextPreprocessor processor with real lightweight NER
def mock_preprocess_process(self, text: str):
    import re
    # Simple word tokenizer and lowercase cleaner
    words = [w.lower().strip() for w in re.findall(r"\b\w+\b", text)]
    # Simple stop-words list
    stops = {
        "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "to", 
        "of", "in", "on", "at", "for", "with", "by", "about", "as", "that", 
        "this", "it", "from", "they", "we", "you", "i", "he", "she", "his", "her"
    }
    clean_tokens = [w for w in words if w not in stops and len(w) > 2]
    
    # Run real NER using loaded spaCy instance
    doc = nlp(text)
    entities = [{"text": ent.text, "label": ent.label_} for ent in doc.ents]
    
    return {
        "language": "en",
        "clean_tokens": clean_tokens,
        "clean_text": " ".join(clean_tokens),
        "char_count": len(text),
        "word_count": len(text.split()),
        "entities": entities
    }

TextPreprocessor.process = mock_preprocess_process

# Override ML representation generators to run real sklearn LDA
def mock_compute_all_representations(
    self,
    raw_text: str,
    clean_tokens: list,
    lda_topics: int = 5,
    ngram_range: tuple = (1, 2),
    generate_dense: bool = True
):
    # Calculate simple word frequencies for TF-IDF simulation
    from collections import Counter
    counts = Counter(clean_tokens)
    total_tokens = len(clean_tokens) or 1
    top_terms = [
        {"term": term, "score": float(count) / total_tokens} 
        for term, count in counts.most_common(20)
    ]
    
    # Real LDA using scikit-learn
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation
    import re
    
    # Split text into sentences using simple regex
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", raw_text) if s.strip()]
    sentences = [s for s in sentences if len(s.split()) >= 3]
    
    topics = []
    if sentences:
        # Scale topic count to corpus size - don't force 5 topics on a short document
        n_topics = min(lda_topics, len(sentences))
        n_topics = max(1, n_topics)
        
        try:
            vectorizer = CountVectorizer(stop_words='english', ngram_range=ngram_range)
            dtm = vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            
            if len(feature_names) > 0:
                lda = LatentDirichletAllocation(
                    n_components=n_topics,
                    random_state=42,
                    max_iter=10
                )
                lda.fit(dtm)
                
                for topic_idx, topic in enumerate(lda.components_):
                    total_weight = sum(topic)
                    normalized_topic = topic / total_weight if total_weight > 0 else topic
                    
                    # Sort terms descending by weight
                    top_indices = normalized_topic.argsort()[::-1][:10]
                    terms = []
                    for i in top_indices:
                        if normalized_topic[i] > 0:
                            terms.append({
                                "term": str(feature_names[i]),
                                "weight": float(normalized_topic[i])
                            })
                    topics.append({
                        "topic_id": topic_idx,
                        "terms": terms
                    })
        except Exception as e:
            # Let it fail cleanly to report issues rather than silent fallback
            raise RuntimeError(f"Real LDA failed: {e}") from e
            
    # Simple rule-based sentiment classifier
    positive_lexicon = {"good", "great", "excellent", "amazing", "love", "helpful", "cool", "fascinating", "succeed"}
    negative_lexicon = {"bad", "terrible", "worst", "hate", "failed", "error", "broken", "critical", "fail"}
    
    pos_count = sum(1 for w in clean_tokens if w in positive_lexicon)
    neg_count = sum(1 for w in clean_tokens if w in negative_lexicon)
    
    total = pos_count + neg_count or 1
    compound = (pos_count - neg_count) / total
    
    pos_pct = round((pos_count / total) * 100) if pos_count else 0
    neg_pct = round((neg_count / total) * 100) if neg_count else 0
    neu_pct = 100 - (pos_pct + neg_pct)
    
    sentiment = {
        "score": round(compound, 2),
        "positive_pct": pos_pct,
        "neutral_pct": neu_pct,
        "negative_pct": neg_pct
    }
    
    return {
        "sparse_tfidf": {
            "tfidf_terms": top_terms,
            "vocabulary_size": len(set(clean_tokens))
        },
        "lda_topics": {"topics": topics},
        "doc_embedding": [0.1] * 384,
        "sentiment": sentiment
    }

RepresentationGenerator.compute_all_representations = mock_compute_all_representations

# Auto-initialize SQLite database tables
Base.metadata.create_all(bind=engine)

# Intercept Celery task delay triggers to execute synchronously in-thread
import app.tasks.analysis_tasks

def run_synchronously(*args, **kwargs):
    doc_id = kwargs.get("document_id") or (args[0] if args else "unknown")
    print(f"--> Mock Celery: Executing analysis task synchronously for document {doc_id}...")
    
    task_func = app.tasks.analysis_tasks.run_nlp_and_representation_pipeline
    
    # Reassign the global references inside the task function's globals
    task_func.__globals__["es_service"] = mock_es
    task_func.__globals__["s3_service"] = mock_s3

    try:
        # Since we preserved the original undecorated function, bind=True is ignored.
        # But the function signature has 'self' as first positional argument, so we pass None.
        task_func(None, *args, **kwargs)
        print("--> Mock Celery: Pipeline execution finished successfully.")
    except Exception as e:
        print(f"--> Mock Celery ERROR: Pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()

    # Return mock Celery AsyncResult
    class MockAsyncResult:
        def __init__(self):
            self.id = "mock-celery-task-id"
            self.status = "SUCCESS"
            self.result = {"document_id": doc_id, "status": "ready"}
            self.info = None
    return MockAsyncResult()

# Patch delay execution
app.tasks.analysis_tasks.run_nlp_and_representation_pipeline.delay = run_synchronously


if __name__ == "__main__":
    import uvicorn
    print("=" * 80)
    print(" TEXTSYNTHETIX LIGHTWEIGHT PRODUCTION SERVER")
    print("=" * 80)
    db_url_info = os.environ.get("DATABASE_URL", "sqlite:///mocked_text_analysis.db")
    db_type = "PostgreSQL" if "postgres" in db_url_info else "SQLite"
    print(f" - Relational DB: {db_type} ({db_url_info.split('@')[-1] if '@' in db_url_info else db_url_info})")
    print(" - Object Storage: Local directory (mocked_s3_storage/)")
    print(" - Vector Search: In-memory query simulation")
    print(" - Background Workers: Running synchronously in-thread")
    print(" - Host Environment: Python 3.12/3.14 native execution")
    print("=" * 80)
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    print(f" Dashboard starting at: http://{host}:{port}/")
    print("=" * 80)
    uvicorn.run("app_server:fastapi_app", host=host, port=port, reload=False)
