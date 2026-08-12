import io
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings


class S3Service:
    def __init__(self):
        # Setup the boto3 s3 client.
        # endpoint_url is passed if using MinIO, otherwise defaults to AWS S3.
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
        )
        self.bucket = settings.S3_BUCKET_NAME

    def ensure_bucket_exists(self):
        """Helper to create the bucket if it does not exist, useful for auto-setup."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            # If bucket not found, create it
            error_code = e.response["Error"]["Code"]
            if error_code in ["404", "NoSuchBucket"]:
                try:
                    if settings.S3_ENDPOINT_URL:
                        # MinIO / LocalStack syntax
                        self.s3_client.create_bucket(Bucket=self.bucket)
                    else:
                        # AWS syntax
                        self.s3_client.create_bucket(
                            Bucket=self.bucket,
                            CreateBucketConfiguration={
                                "LocationConstraint": settings.S3_REGION
                            },
                        )
                except ClientError as create_err:
                    raise RuntimeError(f"Failed to auto-create S3 bucket: {create_err}") from create_err
            else:
                raise e

    def upload_fileobj(self, file_obj, key: str) -> str:
        """Uploads a file-like object to the S3 bucket and returns the s3 URI."""
        self.ensure_bucket_exists()
        try:
            self.s3_client.upload_fileobj(file_obj, self.bucket, key)
            return f"s3://{self.bucket}/{key}"
        except ClientError as e:
            raise RuntimeError(f"S3 upload failed: {e}") from e

    def upload_content(self, content: bytes, key: str) -> str:
        """Uploads raw bytes content to the S3 bucket and returns the s3 URI."""
        self.ensure_bucket_exists()
        try:
            self.s3_client.put_object(Bucket=self.bucket, Key=key, Body=content)
            return f"s3://{self.bucket}/{key}"
        except ClientError as e:
            raise RuntimeError(f"S3 upload failed: {e}") from e

    def get_content(self, key: str) -> bytes:
        """Downloads a file content from S3 as raw bytes."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            raise RuntimeError(f"S3 download failed for key '{key}': {e}") from e

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generates a temporary pre-signed URL to download the asset directly."""
        try:
            # If endpoint is custom (e.g. Docker container), we return a localhost URL for browser/users
            # or the configured endpoint url.
            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            raise RuntimeError(f"Failed to generate pre-signed URL: {e}") from e


s3_service = S3Service()
