from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # NATS Configuration
    nats_url: str = Field(default="nats://localhost:4222", description="NATS server URL")
    
    # S3 Configuration
    s3_endpoint_url: str = Field(default="", description="S3 endpoint URL")
    s3_access_key_id: str = Field(description="S3 access key ID")
    s3_secret_access_key: str = Field(description="S3 secret access key")
    s3_bucket_name: str = Field(description="S3 bucket name")
    s3_region: str = Field(default="us-east-1", description="S3 region")
    
    # Photo Processing
    max_file_size_mb: int = Field(default=10, description="Maximum file size in MB")
    download_timeout_seconds: int = Field(default=30, description="Download timeout in seconds")
    
    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings() 