import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from app.api.deps import get_db, get_current_active_user, RoleChecker
from app.core.s3 import s3_service
from app.models.user import User
from app.models.project import Project, Document
from app.models.provenance import ProvenanceManifest
from app.schemas.analysis import AnalysisTrigger, AnalysisStatusResponse, ProvenanceManifestOut
from app.tasks.analysis_tasks import run_nlp_and_representation_pipeline

router = APIRouter()


@router.post("/documents/{document_id}/analyze", response_model=AnalysisStatusResponse, status_code=status.HTTP_202_ACCEPTED)
def trigger_document_analysis(
    document_id: int,
    trigger: AnalysisTrigger,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["admin", "analyst"]))
):
    """Trigger the asynchronous NLP and representation modeling task for a document. (Admin & Analyst only)."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    project = db.query(Project).filter(Project.id == document.project_id).first()
    if current_user.role != "admin" and project.owner_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not authorized to run analysis on this document")

    # Initially update document status to processing in DB
    document.status = "processing"
    db.commit()

    # Launch Celery background task
    task = run_nlp_and_representation_pipeline.delay(
        document_id=document_id,
        lda_topics=trigger.lda_topics,
        ngram_range_min=trigger.ngram_range_min,
        ngram_range_max=trigger.ngram_range_max,
        generate_dense_embeddings=trigger.generate_dense_embeddings,
        random_seed=trigger.random_seed
    )

    return AnalysisStatusResponse(
        task_id=task.id,
        status=task.status,
        document_id=document_id,
        created_at=datetime.now(timezone.utc)
    )


@router.get("/analysis/tasks/{task_id}", response_model=dict)
def get_analysis_task_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve status of the Celery asynchronous background worker task."""
    result = AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": result.status,
        "result": None,
        "error": None
    }
    if result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.info)
    return response


@router.get("/documents/{document_id}/results", response_model=dict)
def get_document_analysis_results(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve the computed representation outputs (TF-IDF terms, LDA topics) directly from S3 storage."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    project = db.query(Project).filter(Project.id == document.project_id).first()
    if current_user.role != "admin" and project.owner_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not authorized to access this document")

    if document.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Analysis results not ready. Document status is currently: {document.status}"
        )

    # Download representations JSON from S3
    rep_key = f"projects/{document.project_id}/documents/{document.id}/representations.json"
    try:
        results_bytes = s3_service.get_content(rep_key)
        return json.loads(results_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analysis output from S3: {e}"
        )


@router.get("/documents/{document_id}/provenance", response_model=ProvenanceManifestOut)
def get_document_provenance_manifest(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get PostgreSQL database record for provenance, including a pre-signed S3 download URL for the detailed JSON manifest."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
        
    project = db.query(Project).filter(Project.id == document.project_id).first()
    if current_user.role != "admin" and project.owner_id != current_user.id:
         raise HTTPException(status_code=403, detail="Not authorized to access this document")

    # Fetch provenance record from PostgreSQL
    provenance = db.query(ProvenanceManifest).filter(ProvenanceManifest.document_id == document_id).order_by(ProvenanceManifest.created_at.desc()).first()
    if not provenance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No provenance manifest registered for this document. Has analysis been run?"
        )

    # Generate temporary pre-signed URL to S3 JSON artifact
    presigned_url = s3_service.generate_presigned_url(provenance.manifest_s3_key, expires_in=3600)

    # Map database attributes to our API schema
    return ProvenanceManifestOut(
        id=provenance.id,
        document_id=provenance.document_id,
        manifest_s3_key=provenance.manifest_s3_key,
        pipeline_version=provenance.pipeline_version,
        parameters=provenance.parameters,
        created_at=provenance.created_at,
        manifest_url=presigned_url
    )
