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
    InferenceRequest
)
from app.services.photo_downloader import photo_downloader


# Инициализация брокера NATS
broker = NatsBroker(settings.nats_url)

logger = get_logger()


def map_error_code_to_reason(error_code: str) -> str:
    """
    Маппинг кодов ошибок на понятные причины
    
    Args:
        error_code: Код ошибки из photo_downloader
        
    Returns:
        Понятная причина ошибки
    """
    error_mapping = {
        "TELEGRAM_API_ERROR": "telegram_api_error",
        "INVALID_TELEGRAM_URL": "invalid_url",


        "DOWNLOAD_HTTP_ERROR": "download_failed",
        "DOWNLOAD_TIMEOUT": "download_timeout",
        "UNEXPECTED_ERROR": "processing_error",
        "INTERNAL_ERROR": "internal_error",
        "BATCH_PROCESSING_ERROR": "batch_error",
        "INFERENCE_PROCESSING_ERROR": "inference_error",

        "UNSUPPORTED_FORMAT": "unsupported_format",  # Для неподдерживаемых форматов

    }
    
    return error_mapping.get(error_code, "general")


@asynccontextmanager
async def lifespan(app: FastStream):
    """Жизненный цикл приложения"""
    logger.info("Starting Image Downloader service...")
    yield
    logger.info("Shutting down Image Downloader service...")


app = FastStream(broker, lifespan=lifespan)


@broker.subscriber("ms.preparing.prod")
async def handle_batch_training_photos(
    request: PhotoUploadRequest,
) -> None:
    """
    Обработчик для batch загрузки фотографий для тренировки
    
    Args:
        request: Запрос на batch загрузку фотографий для тренировки (новый формат)
    """
    data = request.data
    logger.info(f"Received training batch upload request: avatar_id={data.avatar_id}, "
               f"batch_size={len(data.report)}")
    
    try:
        # Обрабатываем фотографии напрямую
        result = await photo_downloader.process_photos(request)
        
        # Конвертируем результат в новый формат
        if isinstance(result, PhotoUploadError):
            logger.error(f"Training batch upload failed for avatar_id {data.avatar_id}: {result.error}")
            
            # Создаем ответ в новом формате с ошибками
            error_report = []
            for report_item in data.report:
                error_report.append({
                    "file_id": report_item.file_id,
                    "mime_type": report_item.mime_type,
                    "media_type": report_item.media_type,
                    "status": "error",
                    "reason": map_error_code_to_reason("BATCH_PROCESSING_ERROR")
                })
            
            response_payload = {
                "data": {
                    "user_id": data.user_id,
                    "bot_id": data.bot_id,
                    "batch_id": data.batch_id,
                    "avatar_id": data.avatar_id,
                    "report": error_report
                }
            }
            
            response_headers = {
                "Tg-Event": "on_preparing_error",
                "Version": "v1"
            }
            
            await broker.publish({
                "subject": "ms.preparing.prod",
                "payload": response_payload,
                "headers": response_headers
            }, "ms.preparing.prod")
            
        else:
            logger.info(f"Training batch upload successful for avatar_id {data.avatar_id}: "
                       f"{result.successful_files}/{result.total_files} files uploaded "
                       f"in {result.processing_time:.2f}s")
            
            # Создаем ответ в новом формате с успешными результатами
            success_report = []
            for i, upload_result in enumerate(result.successful_uploads):
                # Находим соответствующий report_item
                original_report = data.report[i] if i < len(data.report) else data.report[0]
                
                success_report.append({
                    "file_id": upload_result.file_id,
                    "mime_type": upload_result.content_type,
                    "media_type": original_report.media_type,
                    "properties": {
                        "width": upload_result.width,
                        "height": upload_result.height,
                        "file_size": upload_result.file_size,
                        "s3_key": upload_result.s3_key
                    },
                    "status": "success",
                    "reason": None
                })
            
            # Добавляем ошибки если есть
            for error_upload in result.failed_uploads:
                success_report.append({
                    "file_id": error_upload.file_id,
                    "mime_type": "image/jpeg",  # Значение по умолчанию
                    "media_type": "photo",  # Значение по умолчанию
                    "status": "error",
                    "reason": map_error_code_to_reason(error_upload.error_code)
                })
            
            response_payload = {
                "data": {
                    "user_id": data.user_id,
                    "bot_id": data.bot_id,
                    "batch_id": data.batch_id,
                    "avatar_id": data.avatar_id,
                    "report": success_report
                }
            }
            
            response_headers = {
                "Tg-Event": "on_preparing_success",
                "Version": "v1"
            }
            
            await broker.publish({
                "subject": "ms.preparing.prod",
                "payload": response_payload,
                "headers": response_headers
            }, "ms.preparing.prod")
            
    except Exception as e:
        logger.error(f"Critical error processing training batch for avatar_id {data.avatar_id}: {e}")
        
        # Отправляем критическую ошибку
        error_report = []
        for report_item in data.report:
            error_report.append({
                "file_id": report_item.file_id,
                "mime_type": report_item.mime_type,
                "media_type": report_item.media_type,
                "status": "error",
                "reason": "processing_error"
            })
        
        response_payload = {
            "data": {
                "user_id": data.user_id,
                "bot_id": data.bot_id,
                "batch_id": data.batch_id,
                "avatar_id": data.avatar_id,
                "report": error_report
            }
        }
        
        response_headers = {
            "Tg-Event": "on_preparing_error",
            "Version": "v1"
        }
        
        await broker.publish({
            "subject": "ms.preparing.prod",
            "payload": response_payload,
            "headers": response_headers
        }, "ms.preparing.prod")


@broker.subscriber("ms.inference.prod")
async def handle_inference_error(
    request: InferenceRequest,
) -> None:
    """
    Обработчик для ошибок inference
    
    Args:
        request: Запрос с ошибкой inference (новый формат)
    """
    data = request.data
    logger.info(f"Received inference error: avatar_id={data.avatar_id}, user_id={data.user_id}, reason={data.reason}")
    
    try:
        # Формируем ответ об ошибке inference
        response_payload = {
            "data": {
                "user_id": data.user_id,
                "avatar_id": data.avatar_id,
                "reason": data.reason
            }
        }
        
        response_headers = {
            "Tg-Event": "on_inference_error",
            "Version": "v1"
        }
        
        # Отправляем ответ
        await broker.publish({
            "subject": "ms.inference.prod",
            "payload": response_payload,
            "headers": response_headers
        }, "ms.inference.prod")
        
        logger.info(f"Inference error processed for avatar_id {data.avatar_id}")
        
    except Exception as e:
        logger.error(f"Critical error processing inference error for avatar_id {data.avatar_id}: {e}")
        
        # Отправляем критическую ошибку
        response_payload = {
            "data": {
                "user_id": data.user_id,
                "avatar_id": data.avatar_id,
                "reason": f"Critical processing error: {str(e)}"
            }
        }
        
        response_headers = {
            "Tg-Event": "on_inference_error",
            "Version": "v1"
        }
        
        await broker.publish({
            "subject": "ms.inference.prod",
            "payload": response_payload,
            "headers": response_headers
        }, "ms.inference.prod")


if __name__ == "__main__":
    asyncio.run(app.run()) 