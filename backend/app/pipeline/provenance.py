import importlib.metadata
import logging
import platform
import sys
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


class ProvenanceTracker:
    PIPELINE_VERSION = "1.0.0"

    @classmethod
    def get_library_versions(cls) -> Dict[str, str]:
        """Dynamically fetch the package versions of the key dependencies."""
        dependencies = [
            "spacy",
            "nltk",
            "scikit-learn",
            "gensim",
            "sentence-transformers",
            "transformers",
            "fastapi",
            "celery",
            "elasticsearch",
            "boto3",
        ]
        versions = {}
        for lib in dependencies:
            # Map standard library imports to package names in metadata if different
            package_name = "scikit-learn" if lib == "scikit-learn" else lib
            try:
                versions[lib] = importlib.metadata.version(package_name)
            except importlib.metadata.PackageNotFoundError:
                try:
                    # Fallback to direct import attribute inspection
                    module = __import__(lib.replace("-", "_"))
                    versions[lib] = getattr(module, "__version__", "unknown")
                except (ImportError, AttributeError):
                    versions[lib] = "not_installed"
        return versions

    @classmethod
    def generate_manifest(
        cls,
        document_id: int,
        raw_text_s3_uri: str,
        results_s3_uri: str,
        run_parameters: Dict[str, Any],
        random_seed: int,
    ) -> Dict[str, Any]:
        """Create a versioned execution manifest containing:
        - Metadata details of python runtime and host OS.
        - Pinned third-party library versions.
        - Configured random seed.
        - Upload locations for the source files and outcome metrics in the S3 tier.
        """
        lib_versions = cls.get_library_versions()
        
        manifest = {
            "manifest_schema_version": "1.0",
            "pipeline_version": cls.PIPELINE_VERSION,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "document_id": document_id,
            "environment": {
                "python_version": sys.version,
                "platform": platform.platform(),
                "system": platform.system(),
                "release": platform.release(),
                "dependencies": lib_versions,
            },
            "parameters": {
                "random_seed": random_seed,
                **run_parameters,
            },
            "data_manifest": {
                "inputs": {
                    "raw_text_s3_uri": raw_text_s3_uri,
                },
                "outputs": {
                    "results_s3_uri": results_s3_uri,
                },
            },
        }
        return manifest
