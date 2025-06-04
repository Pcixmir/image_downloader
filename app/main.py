import asyncio
from contextlib import asynccontextmanager
from typing import Union

from faststream import FastStream
from faststream.nats import NatsBroker

from app.settings.settings import settings
from app.utils.logger import get_logger
from app.schemas.schemas import (
    PhotoUploadRequest, 
    PhotoUploadResult, 
    PhotoUploadError,
    InferencePhotoRequest,
    InferencePhotoResult
)
from app.services.photo_downloader import photo_downloader


# Инициализация брокера NATS
broker = NatsBroker(settings.nats_url)

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastStream):
    """Управление жизненным циклом приложения"""
    # Startup
    logger.info("Photo Downloader Service starting up...")
    
    # Проверяем подключение к S3
    from app.services.s3_service import s3_service
    if not s3_service.check_bucket_exists():
        logger.warning(f"S3 bucket '{settings.s3_bucket_name}' does not exist or is not accessible")
    else:
        logger.info(f"S3 bucket '{settings.s3_bucket_name}' is accessible")
    
    yield
    
    # Shutdown
    logger.info("Photo Downloader Service shutting down...")


app = FastStream(broker, lifespan=lifespan)


@broker.subscriber("photo_upload_train")
@broker.publisher("photo_upload_result")
@broker.publisher("photo_upload_error")
async def handle_batch_training_photos(
    request: PhotoUploadRequest,
) -> Union[PhotoUploadResult, PhotoUploadError]:
    """
    Обработчик для batch загрузки фотографий для тренировки
    
    Args:
        request: Запрос на batch загрузку фотографий для тренировки
        
    Returns:
        Результат обработки batch или ошибка
    """
    logger.info(f"Received training batch upload request: job_id={request.job_id}, batch_size={len(request.photos)}")
    
    try:
        # Обрабатываем batch фотографий
        result = await photo_downloader.process_photos(request)
        
        if isinstance(result, PhotoUploadError):
            logger.error(f"Training batch upload failed for job_id {request.job_id}: {result.error}")
            await broker.publish(result, "photo_upload_error")
        else:
            logger.info(f"Training batch upload successful for job_id {request.job_id}: "
                       f"{result.successful_files}/{result.total_files} files uploaded "
                       f"in {result.processing_time:.2f}s")
            await broker.publish(result, "photo_upload_result")
        
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error processing training batch upload: {e}")
        
        error_result = PhotoUploadError(
            header=request.header,
            bot_id=request.bot_id,
            user_id=request.user_id,
            job_id=request.job_id,
            batch_id=request.batch_id,
            error=str(e),
            error_code="INTERNAL_ERROR",
            failed_files=[photo.file_id for photo in request.photos]
        )
        await broker.publish(error_result, "photo_upload_error")
        return error_result


@broker.subscriber("photo_upload_inf")
@broker.publisher("inference_result")
@broker.publisher("photo_upload_error")
async def handle_inference_photo(
    request: InferencePhotoRequest,
) -> Union[InferencePhotoResult, PhotoUploadError]:
    """
    Обработчик для загрузки одиночного фото для inference
    
    Args:
        request: Запрос на загрузку одного фото для inference
        
    Returns:
        Результат обработки фото или ошибка
    """
    logger.info(f"Received inference photo upload request: job_id={request.job_id}, file_id={request.photo.file_id}")
    
    try:
        # Обрабатываем одно фото
        result = await photo_downloader.process_photos(request)
        
        if isinstance(result, PhotoUploadError):
            logger.error(f"Inference photo upload failed for job_id {request.job_id}: {result.error}")
            await broker.publish(result, "photo_upload_error")
        else:
            logger.info(f"Inference photo upload successful for job_id {request.job_id} "
                       f"in {result.processing_time:.2f}s")
            await broker.publish(result, "inference_result")
        
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error processing inference photo upload: {e}")
        
        error_result = PhotoUploadError(
            header=request.header,
            bot_id=request.bot_id,
            user_id=request.user_id,
            job_id=request.job_id,
            error=str(e),
            error_code="INTERNAL_ERROR",
            failed_files=[request.photo.file_id]
        )
        await broker.publish(error_result, "photo_upload_error")
        return error_result


if __name__ == "__main__":
    asyncio.run(app.run()) 