import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional
import uuid
from datetime import datetime

from app.settings.settings import settings
from app.utils.logger import get_logger

logger = get_logger()


class S3Service:
    """Сервис для работы с S3"""
    
    def __init__(self):
        self._client: Optional[boto3.client] = None
    
    @property
    def client(self) -> boto3.client:
        """Ленивая инициализация S3 клиента"""
        if self._client is None:
            try:
                session = boto3.Session(
                    aws_access_key_id=settings.s3_access_key_id,
                    aws_secret_access_key=settings.s3_secret_access_key,
                    region_name=settings.s3_region
                )
                
                client_kwargs = {
                    'service_name': 's3',
                    'region_name': settings.s3_region
                }
                
                if settings.s3_endpoint_url:
                    client_kwargs['endpoint_url'] = settings.s3_endpoint_url
                
                self._client = session.client(**client_kwargs)
                logger.info("S3 client initialized successfully")
                
            except NoCredentialsError:
                logger.error("S3 credentials not found")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                raise
        
        return self._client
    
    def generate_s3_key(self, chat_id: int, photo_id: Optional[str] = None, 
                       file_extension: str = ".jpg") -> str:
        """Генерирует уникальный ключ для файла в S3"""
        if not photo_id:
            photo_id = str(uuid.uuid4())
        
        timestamp = datetime.now().strftime("%Y/%m/%d")
        return f"photos/{chat_id}/{timestamp}/{photo_id}{file_extension}"
    
    async def upload_file(
        self, 
        file_content: bytes, 
        s3_key: str, 
        content_type: str = "image/jpeg",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Загрузка файла в S3
        
        Args:
            file_content: Содержимое файла в байтах
            s3_key: Ключ для сохранения в S3
            content_type: MIME тип файла
            metadata: Дополнительные метаданные
            
        Returns:
            URL загруженного файла
        """
        try:
            extra_args = {
                'ContentType': content_type,
                'ACL': 'public-read'
            }
            
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Загружаем файл
            self.client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=s3_key,
                Body=file_content,
                **extra_args
            )
            
            # Формируем URL
            if settings.s3_endpoint_url:
                file_url = f"{settings.s3_endpoint_url}/{settings.s3_bucket_name}/{s3_key}"
            else:
                file_url = f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/{s3_key}"
            
            logger.info(f"File uploaded successfully to S3: {s3_key}")
            return file_url
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"S3 upload failed with error {error_code}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}")
            raise
    
    def check_bucket_exists(self) -> bool:
        """Проверка существования bucket"""
        try:
            self.client.head_bucket(Bucket=settings.s3_bucket_name)
            return True
        except ClientError:
            return False


# Глобальный экземпляр сервиса
s3_service = S3Service() 