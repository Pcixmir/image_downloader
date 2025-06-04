import asyncio
import httpx
import os
import time
from typing import List, Tuple, Union
from urllib.parse import urlparse
from app.schemas.schemas import (
    PhotoUploadRequest, 
    PhotoUploadResult, 
    PhotoUploadError,
    InferencePhotoRequest,
    InferencePhotoResult,
    FileUploadResult,
    FileUploadError,
    PhotoFile
)
from app.services.s3_service import s3_service
from app.settings.settings import settings
from app.utils.logger import get_logger

logger = get_logger()


class PhotoDownloader:
    """Сервис для загрузки фотографий в S3: batch для train, одиночных для inference"""
    
    def __init__(self):
        self.max_file_size = settings.max_file_size_mb * 1024 * 1024  # Конвертируем в байты
        self.timeout = settings.download_timeout_seconds
        self.max_concurrent_downloads = getattr(settings, 'max_concurrent_downloads', 5)
        self.max_batch_size = getattr(settings, 'max_batch_size', 100)
        
        # Поддерживаемые типы изображений
        self.supported_content_types = {
            'image/jpeg', 'image/jpg', 'image/png', 
            'image/gif', 'image/webp', 'image/bmp'
        }
    
    async def process_photos(
        self, 
        request: Union[PhotoUploadRequest, InferencePhotoRequest]
    ) -> Union[PhotoUploadResult, InferencePhotoResult, PhotoUploadError]:
        """
        Обработка запроса на загрузку фотографий
        
        Args:
            request: Запрос с данными о фотографиях (batch для train или одиночный для inf)
            
        Returns:
            Результат обработки или критическая ошибка
        """
        start_time = time.time()
        
        # Определяем тип запроса
        if isinstance(request, InferencePhotoRequest):
            return await self._process_single_inference(request, start_time)
        elif isinstance(request, PhotoUploadRequest):
            return await self._process_batch_training(request, start_time)
        else:
            # Runtime safety: этот блок не должен выполняться при правильной типизации
            raise ValueError(f"Unsupported request type: {type(request)}")
    
    async def _get_telegram_file_url(self, file_id: str) -> str:
        """
        Получение прямой ссылки на файл из Telegram через Bot API
        
        Args:
            file_id: ID файла в Telegram или готовый HTTP URL
            
        Returns:
            Прямая ссылка для скачивания файла
            
        Raises:
            Exception: Если не удалось получить информацию о файле
        """
        # Если уже передан готовый URL, используем его
        if file_id.startswith(('http://', 'https://')):
            return file_id
        
        # URL для получения информации о файле
        get_file_url = f"{settings.telegram_api_url}/bot{settings.telegram_bot_token}/getFile"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Запрашиваем информацию о файле
            response = await client.get(get_file_url, params={"file_id": file_id})
            response.raise_for_status()
            
            file_info = response.json()
            
            if not file_info.get("ok"):
                raise Exception(f"Telegram API error: {file_info.get('description', 'Unknown error')}")
            
            file_path = file_info["result"]["file_path"]
            
            # Формируем прямую ссылку для скачивания
            download_url = f"{settings.telegram_api_url}/file/bot{settings.telegram_bot_token}/{file_path}"
            
            return download_url
    
    def _validate_url(self, url: str) -> bool:
        """Валидация URL"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def _generate_error_s3_key(self, photo: PhotoFile, request: Union[PhotoUploadRequest, InferencePhotoRequest]) -> str:
        """Генерация s3_key для ошибок (вынесено в отдельный метод для избежания дублирования)"""
        if photo.s3_key and photo.s3_key.strip():
            return photo.s3_key
        
        return s3_service.generate_s3_key(
            user_id=request.user_id,
            photo_id=photo.file_id
        )
    
    async def _process_single_inference(
        self, 
        request: InferencePhotoRequest, 
        start_time: float
    ) -> Union[InferencePhotoResult, PhotoUploadError]:
        """Обработка одиночного фото для inference"""
        logger.info(f"Processing single inference photo for job_id: {request.job_id}")
        
        try:
            # Обрабатываем одно фото
            result = await self._download_and_upload_photo(request.photo, request)
            
            processing_time = time.time() - start_time
            
            if isinstance(result, FileUploadError):
                logger.error(f"Inference photo upload failed for job_id {request.job_id}: {result.error_message}")
                return PhotoUploadError(
                    header=request.header,
                    bot_id=request.bot_id,
                    user_id=request.user_id,
                    job_id=request.job_id,
                    error=result.error_message,
                    error_code=result.error_code,
                    failed_files=[request.photo.file_id]
                )
            else:
                logger.info(f"Inference photo upload successful for job_id {request.job_id} in {processing_time:.2f}s")
                return InferencePhotoResult(
                    header=request.header,
                    bot_id=request.bot_id,
                    user_id=request.user_id,
                    job_id=request.job_id,
                    upload_result=result,
                    processing_time=processing_time,
                    message="Photo uploaded successfully"
                )
                
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Critical error processing inference photo for job_id {request.job_id}: {e}")
            
            return PhotoUploadError(
                header=request.header,
                bot_id=request.bot_id,
                user_id=request.user_id,
                job_id=request.job_id,
                error=str(e),
                error_code="INFERENCE_PROCESSING_ERROR",
                failed_files=[request.photo.file_id]
            )
    
    async def _process_batch_training(
        self, 
        request: PhotoUploadRequest, 
        start_time: float
    ) -> Union[PhotoUploadResult, PhotoUploadError]:
        """Обработка batch фотографий для тренировки"""
        logger.info(f"Processing batch training photos for job_id: {request.job_id}, batch_size: {len(request.photos)}")
        
        try:
            # Валидация batch
            await self._validate_batch(request)
            
            # Обработка фотографий с ограничением параллельности
            successful_uploads = []
            failed_uploads = []
            total_size = 0
            
            # Создаем семафор для ограничения параллельных загрузок
            semaphore = asyncio.Semaphore(self.max_concurrent_downloads)
            
            # Запускаем параллельную обработку
            tasks = []
            for photo in request.photos:
                task = self._process_single_photo(photo, request, semaphore)
                tasks.append(task)
            
            # Ждем завершения всех задач
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Обрабатываем результаты
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Unexpected error in batch processing: {result}")
                    failed_uploads.append(FileUploadError(
                        file_id="unknown",
                        s3_key="unknown",
                        error_message=str(result),
                        error_code="UNEXPECTED_ERROR"
                    ))
                elif isinstance(result, FileUploadResult):
                    successful_uploads.append(result)
                    total_size += result.file_size
                elif isinstance(result, FileUploadError):
                    failed_uploads.append(result)
            
            processing_time = time.time() - start_time
            
            logger.info(f"Batch processing completed for job_id: {request.job_id}. "
                       f"Success: {len(successful_uploads)}, Failed: {len(failed_uploads)}, "
                       f"Time: {processing_time:.2f}s")
            
            return PhotoUploadResult(
                header=request.header,
                bot_id=request.bot_id,
                user_id=request.user_id,
                job_id=request.job_id,
                batch_id=request.batch_id,
                total_files=len(request.photos),
                successful_files=len(successful_uploads),
                failed_files=len(failed_uploads),
                successful_uploads=successful_uploads,
                failed_uploads=failed_uploads,
                processing_time=processing_time,
                total_size=total_size,
                message=f"Batch processing completed: {len(successful_uploads)}/{len(request.photos)} files successful"
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Critical error processing batch for job_id {request.job_id}: {e}")
            
            return PhotoUploadError(
                header=request.header,
                bot_id=request.bot_id,
                user_id=request.user_id,
                job_id=request.job_id,
                batch_id=request.batch_id,
                error=str(e),
                error_code="BATCH_PROCESSING_ERROR",
                failed_files=[photo.file_id for photo in request.photos]
            )
    
    async def _validate_batch(self, request: PhotoUploadRequest) -> None:
        """Валидация batch запроса"""
        if not request.photos:
            raise ValueError("Batch cannot be empty")
        
        if len(request.photos) > self.max_batch_size:
            raise ValueError(f"Batch size exceeds maximum limit of {self.max_batch_size} files")
        
        logger.debug(f"Batch validation passed for {len(request.photos)} photos")
    
    async def _process_single_photo(
        self, 
        photo: PhotoFile, 
        request: PhotoUploadRequest, 
        semaphore: asyncio.Semaphore
    ) -> Union[FileUploadResult, FileUploadError]:
        """
        Обработка одной фотографии с семафором для ограничения параллельности
        """
        async with semaphore:
            return await self._download_and_upload_photo(photo, request)
    
    async def _download_and_upload_photo(
        self, 
        photo: PhotoFile, 
        request: Union[PhotoUploadRequest, InferencePhotoRequest]
    ) -> Union[FileUploadResult, FileUploadError]:
        """
        Скачивание и загрузка одной фотографии
        """
        start_time = time.time()
        
        try:
            logger.debug(f"Processing photo {photo.file_id}")
            
            # Генерируем s3_key если он пустой
            s3_key = photo.s3_key
            if not s3_key or s3_key.strip() == "":
                # Определяем расширение файла из original_filename или используем .jpg по умолчанию
                file_extension = ".jpg"  # По умолчанию
                if photo.original_filename:
                    _, ext = os.path.splitext(photo.original_filename)
                    if ext:
                        file_extension = ext.lower()
                
                s3_key = s3_service.generate_s3_key(
                    user_id=request.user_id,
                    photo_id=photo.file_id,
                    file_extension=file_extension
                )
                logger.debug(f"Generated s3_key for photo {photo.file_id}: {s3_key}")
            
            # Формируем полный путь в S3
            full_s3_key = self._build_s3_path(request, s3_key)
            
            # Получаем прямую ссылку для скачивания из Telegram
            try:
                photo_url = await self._get_telegram_file_url(photo.file_id)
                logger.debug(f"Got Telegram download URL for {photo.file_id}")
            except Exception as e:
                logger.error(f"Failed to get Telegram file URL for {photo.file_id}: {e}")
                return FileUploadError(
                    file_id=photo.file_id,
                    s3_key=full_s3_key,
                    error_message=f"Failed to get Telegram file URL: {str(e)}",
                    error_code="TELEGRAM_API_ERROR"
                )
            
            # Валидируем полученный URL
            if not self._validate_url(photo_url):
                return FileUploadError(
                    file_id=photo.file_id,
                    s3_key=full_s3_key,
                    error_message=f"Invalid Telegram file URL: {photo_url}",
                    error_code="INVALID_TELEGRAM_URL"
                )
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Скачиваем фото
                response = await client.get(photo_url)
                response.raise_for_status()
                
                # Проверяем размер файла
                content_length = len(response.content)
                if content_length > self.max_file_size:
                    return FileUploadError(
                        file_id=photo.file_id,
                        s3_key=full_s3_key,
                        error_message=f"File size {content_length} exceeds maximum {self.max_file_size}",
                        error_code="FILE_TOO_LARGE"
                    )
                
                # Определяем и валидируем content type
                content_type = response.headers.get('content-type', 'image/jpeg')
                if content_type not in self.supported_content_types:
                    logger.warning(f"Unsupported content type {content_type} for file {photo.file_id}, using image/jpeg")
                    content_type = 'image/jpeg'
                
                # Формируем метаданные
                metadata = {
                    'bot_id': str(request.bot_id),
                    'user_id': str(request.user_id),
                    'job_id': str(request.job_id),
                    'file_id': photo.file_id,
                    'header': request.header,
                    'original_filename': photo.original_filename or '',
                    'processing_time': str(time.time() - start_time)
                }
                
                # Добавляем batch_id только для batch запросов
                if hasattr(request, 'batch_id') and request.batch_id:
                    metadata['batch_id'] = str(request.batch_id)
                
                # Загружаем в S3
                file_url = await s3_service.upload_file(
                    file_content=response.content,
                    s3_key=full_s3_key,
                    content_type=content_type,
                    metadata=metadata
                )
                
                upload_time = time.time() - start_time
                
                logger.info(f"Successfully processed photo {photo.file_id} in {upload_time:.2f}s")
                
                return FileUploadResult(
                    file_id=photo.file_id,
                    s3_key=full_s3_key,
                    s3_url=file_url,
                    original_filename=photo.original_filename,
                    file_size=content_length,
                    upload_time=upload_time,
                    content_type=content_type
                )
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error downloading file: {e.response.status_code}"
            logger.error(f"Failed to download photo {photo.file_id}: {error_msg}")
            return FileUploadError(
                file_id=photo.file_id,
                s3_key=self._build_s3_path(request, self._generate_error_s3_key(photo, request)),
                error_message=error_msg,
                error_code="DOWNLOAD_HTTP_ERROR"
            )
        except httpx.TimeoutException:
            error_msg = f"Timeout downloading file after {self.timeout}s"
            logger.error(f"Failed to download photo {photo.file_id}: {error_msg}")
            return FileUploadError(
                file_id=photo.file_id,
                s3_key=self._build_s3_path(request, self._generate_error_s3_key(photo, request)),
                error_message=error_msg,
                error_code="DOWNLOAD_TIMEOUT"
            )
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Failed to process photo {photo.file_id}: {error_msg}")
            return FileUploadError(
                file_id=photo.file_id,
                s3_key=self._build_s3_path(request, self._generate_error_s3_key(photo, request)),
                error_message=error_msg,
                error_code="UNEXPECTED_ERROR"
            )
    
    def _build_s3_path(self, request: Union[PhotoUploadRequest, InferencePhotoRequest], s3_key: str) -> str:
        """Формирование полного пути в S3"""
        if request.header == "train":
            # Для тренировки: bot_id->user_id->job_id
            return f"{request.bot_id}/{request.user_id}/{request.job_id}/{s3_key}"
        else:
            # Для inference: uploads/inf/bot_id/user_id/job_id (без batch_id для одиночных фото)
            return f"uploads/{request.header}/{request.bot_id}/{request.user_id}/{request.job_id}/{s3_key}"


# Глобальный экземпляр сервиса
photo_downloader = PhotoDownloader()