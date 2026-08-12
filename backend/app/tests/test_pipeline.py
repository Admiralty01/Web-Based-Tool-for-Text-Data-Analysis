import pytest
from app.pipeline.preprocess import TextPreprocessor
from app.pipeline.representation import RepresentationGenerator
from app.pipeline.provenance import ProvenanceTracker


def test_text_preprocessor():
    """Verify that TextPreprocessor correctly normalizes, filters stop-words, lemmatizes and detects language."""
    preprocessor = TextPreprocessor()
    text = "The quick brown fox jumps over the lazy dogs. Machine learning is fascinating!"
    
    results = preprocessor.process(text)
    
    # Check language detection
    assert results["language"] == "en"
    
    # Check character and word counts
    assert results["char_count"] == len(text)
    assert results["word_count"] == len(text.split())
    
    # Check cleaning and lemmatization (nouns/verbs normalized, stop-words like 'the', 'is', 'over' removed)
    clean_tokens = results["clean_tokens"]
    assert "quick" in clean_tokens
    assert "brown" in clean_tokens
    assert "fox" in clean_tokens
    assert "jump" in clean_tokens  # lemma of jumps
    assert "lazy" in clean_tokens
    assert "dog" in clean_tokens   # lemma of dogs
    
    # Stop-words should not be present
    assert "the" not in clean_tokens
    assert "is" not in clean_tokens
    
    # Clean text should be space-joined tokens
    assert results["clean_text"] == " ".join(clean_tokens)


def test_representation_generator_sparse_tfidf():
    """Test TF-IDF sparse feature extraction on sample sentences."""
    generator = RepresentationGenerator()
    sentences = [
        "natural language processing is cool",
        "machine learning and deep learning models",
        "processing textual data using algorithms"
    ]
    
    res = generator.generate_sparse_tfidf(sentences, ngram_range=(1, 1))
    
    assert res["vocabulary_size"] > 0
    assert len(res["tfidf_terms"]) > 0
    # Top terms should have terms and scores
    first_term = res["tfidf_terms"][0]
    assert "term" in first_term
    assert "score" in first_term
    assert isinstance(first_term["score"], float)


def test_representation_generator_lda_topics():
    """Test LDA topic modeling on tokenized sentences."""
    generator = RepresentationGenerator(random_seed=42)
    token_lists = [
        ["natural", "language", "processing"],
        ["machine", "learning", "algorithms"],
        ["deep", "learning", "neural", "networks"],
        ["neural", "language", "models"]
    ]
    
    res = generator.generate_lda_topics(token_lists, num_topics=2)
    
    assert "topics" in res
    assert len(res["topics"]) == 2
    topic_zero = res["topics"][0]
    assert topic_zero["topic_id"] == 0
    assert len(topic_zero["terms"]) > 0
    assert "term" in topic_zero["terms"][0]
    assert "weight" in topic_zero["terms"][0]


def test_dense_embeddings_fallback():
    """Verify that dense embedding generation runs and fails gracefully into deterministic mock embeddings."""
    generator = RepresentationGenerator(random_seed=100)
    text = "Extract vector coordinates from this text sequence."
    
    # Execute generation
    embeddings = generator.generate_dense_embeddings(text, dims=384)
    
    # Verify response contains exactly 1 vector of dimension 384
    assert len(embeddings) == 1
    vector = embeddings[0]
    assert len(vector) == 384
    assert isinstance(vector[0], float)
    
    # Verify unit-length normalization: dot product of vector with itself should equal ~1.0
    dot_product = sum(x * x for x in vector)
    assert pytest.approx(dot_product, abs=1e-5) == 1.0


def test_provenance_tracker():
    """Verify that ProvenanceTracker gathers operating system, environment versions, and run metrics correctly."""
    run_params = {
        "lda_topics": 5,
        "ngram_range_min": 1,
        "ngram_range_max": 2,
        "generate_dense_embeddings": True
    }
    seed = 101
    
    manifest = ProvenanceTracker.generate_manifest(
        document_id=5,
        raw_text_s3_uri="s3://test-bucket/raw/5.txt",
        results_s3_uri="s3://test-bucket/out/5.json",
        run_parameters=run_params,
        random_seed=seed
    )
    
    # Verify structure
    assert manifest["manifest_schema_version"] == "1.0"
    assert manifest["pipeline_version"] == "1.0.0"
    assert manifest["document_id"] == 5
    assert "timestamp" in manifest
    
    # Parameters check
    assert manifest["parameters"]["random_seed"] == seed
    assert manifest["parameters"]["lda_topics"] == 5
    
    # Environment checks
    assert "python_version" in manifest["environment"]
    assert "dependencies" in manifest["environment"]
    # Check that key libraries are recorded
    assert "spacy" in manifest["environment"]["dependencies"]
    assert "nltk" in manifest["environment"]["dependencies"]
    
    # S3 manifests checks
    assert manifest["data_manifest"]["inputs"]["raw_text_s3_uri"] == "s3://test-bucket/raw/5.txt"
    assert manifest["data_manifest"]["outputs"]["results_s3_uri"] == "s3://test-bucket/out/5.json"


def test_representation_generator_sentiment():
    """Verify that sentiment analyzer returns structured VADER score matrices."""
    generator = RepresentationGenerator()
    text = "NLTK VADER is absolutely amazing and incredibly helpful. I love this tool!"
    
    sentiment = generator.generate_sentiment(text)
    
    assert "score" in sentiment
    assert "positive_pct" in sentiment
    assert "neutral_pct" in sentiment
    assert "negative_pct" in sentiment
    assert sentiment["score"] > 0.5  # Should be positive
    
    # Check compute_all_representations integrates it
    res = generator.compute_all_representations(
        raw_text=text,
        clean_tokens=["nltk", "vader", "amazing", "helpful", "love", "tool"],
        lda_topics=2,
        ngram_range=(1, 1),
        generate_dense=False
    )
    assert "sentiment" in res
    assert res["sentiment"]["score"] == sentiment["score"]
