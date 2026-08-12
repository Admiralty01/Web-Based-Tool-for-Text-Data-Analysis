import json
import logging
from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.project import Document
from app.models.provenance import ProvenanceManifest
from app.core.s3 import s3_service
from app.core.elasticsearch import es_service
from app.pipeline.preprocess import TextPreprocessor
from app.pipeline.representation import RepresentationGenerator
from app.pipeline.provenance import ProvenanceTracker

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def run_nlp_and_representation_pipeline(
    self,
    document_id: int,
    lda_topics: int = 5,
    ngram_range_min: int = 1,
    ngram_range_max: int = 2,
    generate_dense_embeddings: bool = True,
    random_seed: int = 42,
):
    """Orchestrate the 3-tier text processing background worker task.
    
    1. Downloads raw text from S3-compatible storage.
    2. Executes deterministic NLP preprocessing (spaCy & NLTK).
    3. Generates plural representations: sparse count TF-IDF n-grams, LDA topics, dense embeddings.
    4. Indexes the text and document embeddings in Elasticsearch for hybrid search.
    5. Saves full analysis results and a reproducibility provenance manifest back to S3.
    6. Updates database states and registers the execution manifest in PostgreSQL.
    """
    logger.info(f"Starting NLP pipeline for document ID: {document_id}")
    db = SessionLocal()
    
    try:
        # 1. Fetch document from database
        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document with ID {document_id} not found in database.")
            
        # Update status to processing
        document.status = "processing"
        db.commit()
        
        # 2. Download raw text from S3
        logger.info(f"Downloading raw text from S3 key: {document.s3_key}")
        raw_bytes = s3_service.get_content(document.s3_key)
        raw_text = raw_bytes.decode("utf-8")
        
        # 3. Preprocess text (Language Detection, Tokenization, Lemmatization, Stop-Words)
        logger.info("Executing spaCy/NLTK Preprocessing Pipeline...")
        preprocessor = TextPreprocessor()
        prep_results = preprocessor.process(raw_text)
        
        # Update document profiling metadata in database
        document.language = prep_results["language"]
        document.char_count = prep_results["char_count"]
        document.word_count = prep_results["word_count"]
        db.commit()
        
        # 4. Generate representations (TF-IDF, LDA, Sentence-BERT Embeddings)
        logger.info("Generating plural representation models (Sparse, Probabilistic, Dense)...")
        generator = RepresentationGenerator(random_seed=random_seed)
        representations = generator.compute_all_representations(
            raw_text=raw_text,
            clean_tokens=prep_results["clean_tokens"],
            lda_topics=lda_topics,
            ngram_range=(ngram_range_min, ngram_range_max),
            generate_dense=generate_dense_embeddings
        )
        
        # 5. Upload representations JSON to S3
        rep_key = f"projects/{document.project_id}/documents/{document.id}/representations.json"
        logger.info(f"Uploading representations file to S3: {rep_key}")
        representations_data = {
            "preprocessed_stats": {
                "language": prep_results["language"],
                "char_count": prep_results["char_count"],
                "word_count": prep_results["word_count"],
            },
            "entities": prep_results.get("entities", []),
            "sparse_tfidf": representations["sparse_tfidf"],
            "lda_topics": representations["lda_topics"],
            "sentiment": representations["sentiment"]
        }
        s3_service.upload_content(
            content=json.dumps(representations_data).encode("utf-8"),
            key=rep_key
        )
        
        # 6. Upload Provenance Manifest JSON to S3
        prov_key = f"projects/{document.project_id}/documents/{document.id}/provenance_manifest.json"
        logger.info(f"Generating and uploading versioned provenance manifest to S3: {prov_key}")
        
        run_params = {
            "lda_topics": lda_topics,
            "ngram_range_min": ngram_range_min,
            "ngram_range_max": ngram_range_max,
            "generate_dense_embeddings": generate_dense_embeddings
        }
        
        manifest_data = ProvenanceTracker.generate_manifest(
            document_id=document.id,
            raw_text_s3_uri=f"s3://{s3_service.bucket}/{document.s3_key}",
            results_s3_uri=f"s3://{s3_service.bucket}/{rep_key}",
            run_parameters=run_params,
            random_seed=random_seed
        )
        
        s3_service.upload_content(
            content=json.dumps(manifest_data).encode("utf-8"),
            key=prov_key
        )
        
        # 7. Record Provenance manifest reference in PostgreSQL
        logger.info("Registering provenance record in PostgreSQL...")
        provenance = ProvenanceManifest(
            document_id=document.id,
            manifest_s3_key=prov_key,
            pipeline_version=ProvenanceTracker.PIPELINE_VERSION,
            parameters=run_params
        )
        db.add(provenance)
        db.commit()
        
        # 8. Index document in Elasticsearch for hybrid search
        index_name = f"project_{document.project_id}"
        logger.info(f"Indexing preprocessed text in Elasticsearch index: {index_name}")
        
        # Ensure the project index is created with custom mappings
        # (dims=384 corresponds to Sentence-BERT all-MiniLM-L6-v2)
        es_service.create_index(index_name=index_name, dims=384)
        
        # We index the document if it has valid dense embedding.
        # If generate_dense_embeddings was False, we supply a dummy vector of 0s.
        embedding = representations["doc_embedding"]
        if not embedding:
            embedding = [0.0] * 384
            
        es_service.index_document(
            index_name=index_name,
            document_id=str(document.id),
            title=document.title,
            content=raw_text,
            clean_content=prep_results["clean_text"],
            embedding=embedding
        )
        
        # 9. Update document status to ready
        document.status = "ready"
        db.commit()
        logger.info(f"Document {document_id} pipeline completed successfully.")
        
        return {
            "document_id": document_id,
            "status": "ready",
            "representations_s3_key": rep_key,
            "provenance_s3_key": prov_key
        }
        
    except Exception as e:
        logger.exception(f"Error running NLP pipeline for document {document_id}: {e}")
        # Rollback database changes and mark document as failed
        db.rollback()
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = "failed"
                document.error_message = str(e)
                db.commit()
        except Exception as db_err:
            logger.error(f"Failed to record error state in DB for document {document_id}: {db_err}")
            
        # Retry celery task if appropriate
        try:
            self.retry(exc=e)
        except Exception:
            raise e
            
    finally:
        db.close()
