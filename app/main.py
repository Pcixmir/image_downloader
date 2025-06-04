import asyncio
from contextlib import asynccontextmanager
from threading import Thread

from faststream import FastStream
from faststream.nats import NatsBroker

from app.settings.settings import settings
from app.utils.logger import get_logger, get_logger_aggregator
from app.schemas.schemas import PhotoUploadRequest, PhotoUploadResult, PhotoUploadError
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


@broker.subscriber("photo_upload")
@broker.publisher("photo_upload_result")
@broker.publisher("photo_upload_error")
async def handle_photo_upload(
    request: PhotoUploadRequest,
) -> PhotoUploadResult | PhotoUploadError:
    """
    Обработчик сообщений для загрузки фотографий
    
    Args:
        request: Запрос на загрузку фотографий
        
    Returns:
        Результат обработки или ошибка
    """
    logger.info(f"Received photo upload request: {request.job_id}")
    
    try:
        # Обрабатываем фотографии
        result = await photo_downloader.process_photos(request)
        
        if isinstance(result, PhotoUploadError):
            logger.error(f"Photo upload failed for job_id {request.job_id}: {result.error}")
            await broker.publish(result, "photo_upload_error")
        else:
            logger.info(f"Photo upload successful for job_id {request.job_id}")
            await broker.publish(result, "photo_upload_result")
        
        return result
        
    except Exception as e:
        logger.error(f"Unexpected error processing photo upload: {e}")
        error_result = PhotoUploadError(
            header=request.header,
            file_id=request.file_id,
            bot_id=request.bot_id,
            user_id=request.user_id,
            job_id=request.job_id,
            error=str(e),
            error_code="INTERNAL_ERROR",
            failed_files=request.file_id
        )
        await broker.publish(error_result, "photo_upload_error")
        return error_result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 