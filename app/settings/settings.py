from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # NATS Configuration
    nats_url: str = Field(default="nats://localhost:4222", description="NATS server URL")
    
    # Telegram Bot Configuration
    telegram_bot_token: str = Field(description="Telegram Bot Token")
    telegram_api_url: str = Field(default="https://api.telegram.org", description="Telegram API base URL")
    
    # S3 Configuration
    s3_endpoint_url: str = Field(default="", description="S3 endpoint URL")
    s3_access_key_id: str = Field(description="S3 access key ID")
    s3_secret_access_key: str = Field(description="S3 secret access key")
    s3_bucket_name: str = Field(description="S3 bucket name")
    s3_region: str = Field(default="us-east-1", description="S3 region")
    


    download_timeout_seconds: int = Field(default=30, description="Download timeout in seconds")
    
    # Batch Processing
    max_concurrent_downloads: int = Field(default=5, description="Maximum concurrent downloads per batch")
    max_batch_size: int = Field(default=100, description="Maximum number of files per batch")
    batch_processing_timeout: int = Field(default=300, description="Batch processing timeout in seconds")
    
    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Глобальный экземпляр настроек
settings = Settings() 