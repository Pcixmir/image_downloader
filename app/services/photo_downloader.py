import httpx
from typing import List, Tuple
from app.schemas.schemas import PhotoUploadRequest, PhotoUploadResult, PhotoUploadError
from app.services.s3_service import s3_service
from app.settings.settings import settings
from app.utils.logger import get_logger

logger = get_logger()


class PhotoDownloader:
    """Сервис для загрузки фотографий в S3"""
    
    def __init__(self):
        self.max_file_size = settings.max_file_size_mb * 1024 * 1024  # Конвертируем в байты
        self.timeout = settings.download_timeout_seconds
    
    async def process_photos(self, request: PhotoUploadRequest) -> PhotoUploadResult | PhotoUploadError:
        """
        Обработка запроса на загрузку фотографий
        
        Args:
            request: Запрос с данными о фотографиях
            
        Returns:
            Результат обработки или ошибка
        """
        logger.info(f"Processing photo upload request for job_id: {request.job_id}")
        
        if len(request.file_id) != len(request.s3_key):
            error_msg = "Количество file_id и s3_key должно совпадать"
            logger.error(error_msg)
            return PhotoUploadError(
                header=request.header,
                file_id=request.file_id,
                bot_id=request.bot_id,
                chat_id=request.chat_id,
                job_id=request.job_id,
                error=error_msg,
                error_code="VALIDATION_ERROR",
                failed_files=request.file_id
            )
        
        successful_files = []
        successful_keys = []
        successful_urls = []
        failed_files = []
        
        # Обрабатываем каждую фотографию
        for file_id, s3_key in zip(request.file_id, request.s3_key):
            try:
                # Формируем полный путь в S3
                full_s3_key = self._build_s3_path(request, s3_key)
                
                # Скачиваем и загружаем фото
                file_url = await self._download_and_upload_photo(file_id, full_s3_key, request)
                
                successful_files.append(file_id)
                successful_keys.append(full_s3_key)
                successful_urls.append(file_url)
                
                logger.info(f"Successfully processed photo: {file_id}")
                
            except Exception as e:
                logger.error(f"Failed to process photo {file_id}: {e}")
                failed_files.append(file_id)
        
        # Возвращаем результат
        if failed_files:
            return PhotoUploadError(
                header=request.header,
                file_id=failed_files,
                bot_id=request.bot_id,
                chat_id=request.chat_id,
                job_id=request.job_id,
                error=f"Failed to process {len(failed_files)} files",
                error_code="PROCESSING_ERROR",
                failed_files=failed_files
            )
        else:
            return PhotoUploadResult(
                header=request.header,
                file_id=successful_files,
                s3_key=successful_keys,
                s3_url=successful_urls,
                bot_id=request.bot_id,
                chat_id=request.chat_id,
                job_id=request.job_id,
                message=f"Successfully uploaded {len(successful_files)} photos"
            )
    
    def _build_s3_path(self, request: PhotoUploadRequest, s3_key: str) -> str:
        """Формирование полного пути в S3"""
        return f"uploads/{request.header}/{request.bot_id}/{request.chat_id}/{request.job_id}/{s3_key}"
    
    async def _download_and_upload_photo(self, file_id: str, s3_key: str, request: PhotoUploadRequest) -> str:
        """
        Скачивание фото по file_id и загрузка в S3
        
        Args:
            file_id: ID файла для скачивания
            s3_key: Ключ для сохранения в S3
            request: Исходный запрос
            
        Returns:
            URL загруженного файла
        """
        # Здесь должна быть логика получения URL файла по file_id
        # Пока используем file_id как URL (для тестирования)
        photo_url = file_id
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Скачиваем фото
            response = await client.get(photo_url)
            response.raise_for_status()
            
            # Проверяем размер файла
            content_length = len(response.content)
            if content_length > self.max_file_size:
                raise ValueError(f"File size {content_length} exceeds maximum {self.max_file_size}")
            
            # Определяем content type
            content_type = response.headers.get('content-type', 'image/jpeg')
            
            # Формируем метаданные
            metadata = {
                'bot_id': str(request.bot_id),
                'chat_id': str(request.chat_id),
                'job_id': str(request.job_id),
                'file_id': file_id,
                'header': request.header
            }
            
            # Загружаем в S3
            file_url = await s3_service.upload_file(
                file_content=response.content,
                s3_key=s3_key,
                content_type=content_type,
                metadata=metadata
            )
            
            return file_url


# Глобальный экземпляр сервиса
photo_downloader = PhotoDownloader() 