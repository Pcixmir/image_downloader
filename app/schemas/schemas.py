from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, List, Dict, Any, Tuple
from datetime import datetime


class PhotoFile(BaseModel):
    """Файл фотографии для обработки"""
    file_id: str = Field(description="ID файла в Telegram или URL")
    s3_key: str = Field(default="", description="Ключ для S3 (опционально, генерируется автоматически если пустой)")


class BoundingBox(BaseModel):
    """Координаты ограничивающего прямоугольника"""
    TL: Tuple[int, int] = Field(description="Top Left - верхний левый угол")
    TR: Tuple[int, int] = Field(description="Top Right - верхний правый угол") 
    BR: Tuple[int, int] = Field(description="Bottom Right - нижний правый угол")
    BL: Tuple[int, int] = Field(description="Bottom Left - нижний левый угол")


class PhotoProperties(BaseModel):
    """Свойства фотографии"""
    width: int = Field(description="Ширина изображения в пикселях")
    height: int = Field(description="Высота изображения в пикселях")
    bbox: Optional[BoundingBox] = Field(default=None, description="Координаты ограничивающего прямоугольника (опционально)")
    num_faces: Optional[int] = Field(default=None, description="Количество лиц на фото (опционально)")
    face_diagonal: Optional[int] = Field(default=None, description="Диагональ лица в пикселях (опционально)")
    file_size: int = Field(description="Размер файла в байтах")
    s3_key: str = Field(description="Ключ файла в S3")
    



class ReportItem(BaseModel):
    """Элемент отчета о файле"""
    file_id: str = Field(description="ID файла в Telegram")
    mime_type: str = Field(description="MIME тип файла (image/jpg, image/png, etc.)")
    media_type: Literal["photo", "document"] = Field(description="Тип медиа")
    properties: Optional[PhotoProperties] = Field(default=None, description="Свойства фото (только для успешных)")
    status: Literal["success", "error"] = Field(description="Статус обработки файла")
    reason: Optional[str] = Field(default=None, description="Причина ошибки (только для status=error)")
    
    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v, info):
        # reason должен быть заполнен только при status=error
        if info.data.get('status') == 'error' and not v:
            raise ValueError('reason is required when status is error')
        if info.data.get('status') == 'success' and v:
            raise ValueError('reason should be None when status is success')
        return v


class PayloadData(BaseModel):
    """Данные в payload"""
    avatar_id: int = Field(description="ID аватара")
    user_id: int = Field(description="ID пользователя")
    bot_id: int = Field(description="ID бота")
    batch_id: int = Field(description="ID batch")
    avatar_id: int = Field(description="ID аватара")
    report: List[ReportItem] = Field(description="Отчет по файлам", min_length=1)


class MessageHeaders(BaseModel):
    """Заголовки сообщения"""
    tg_event: str = Field(alias="Tg-Event", description="Тип события Telegram")
    version: str = Field(alias="Version", description="Версия API")
    
    class Config:
        populate_by_name = True


class PhotoUploadRequest(BaseModel):
    """Запрос на обработку фотографий (новый формат)"""
    subject: str = Field(description="Тема сообщения", example="ms.preparing.prod")
    payload: Dict[str, PayloadData] = Field(description="Полезная нагрузка с данными")
    headers: MessageHeaders = Field(description="Заголовки сообщения")
    
    @field_validator('payload')
    @classmethod
    def validate_payload_structure(cls, v):
        if 'data' not in v:
            raise ValueError('payload must contain "data" key')
        return v
    
    @property
    def data(self) -> PayloadData:
        """Удобный доступ к данным"""
        return self.payload['data']
    
    @property
    def photos(self) -> List[PhotoFile]:
        """Конвертация report в photos для совместимости с photo_downloader"""
        photos = []
        for report_item in self.data.report:
            photo = PhotoFile(
                file_id=report_item.file_id,
                s3_key="",  # Будет сгенерирован автоматически
            )
            photos.append(photo)
        return photos
    
    @property
    def header(self) -> str:
        """Определение типа операции на основе subject"""
        return "train"  # Всегда train для batch операций
    
    @property
    def bot_id(self) -> int:
        return self.data.bot_id
    
    @property
    def user_id(self) -> int:
        return self.data.user_id
    
    @property
    def avatar_id(self) -> str:
        return str(self.data.avatar_id)
    
    @property
    def batch_id(self) -> str:
        return str(self.data.batch_id)


# Результирующие схемы остаются прежними для совместимости
class FileUploadResult(BaseModel):
    """Результат загрузки одного файла"""
    file_id: str = Field(description="ID файла")
    s3_key: str = Field(description="Ключ в S3")
    s3_url: str = Field(description="URL файла в S3")
    file_size: int = Field(description="Размер файла в байтах")
    upload_time: float = Field(description="Время загрузки файла в секундах")
    content_type: str = Field(default="image/jpeg", description="MIME тип файла")
    width: int = Field(default=0, description="Ширина изображения в пикселях")
    height: int = Field(default=0, description="Высота изображения в пикселях")


class FileUploadError(BaseModel):
    """Ошибка загрузки одного файла"""
    file_id: str = Field(description="ID файла с ошибкой")
    s3_key: str = Field(description="Предполагаемый ключ в S3")
    error_message: str = Field(description="Описание ошибки")
    error_code: str = Field(description="Код ошибки")
    timestamp: datetime = Field(default_factory=datetime.now)


class PhotoUploadResult(BaseModel):
    """Результат успешной batch загрузки фотографий"""
    header: Literal["train"] = Field(description="Тип операции")
    bot_id: int = Field(description="ID бота")
    user_id: int = Field(description="ID пользователя")
    avatar_id: str = Field(description="ID аватара")
    batch_id: Optional[str] = Field(default=None, description="ID batch")
    
    # Статистика batch
    total_files: int = Field(description="Общее количество файлов в batch")
    successful_files: int = Field(description="Количество успешно загруженных файлов")
    failed_files: int = Field(description="Количество файлов с ошибками")
    
    # Детали загруженных файлов
    successful_uploads: List[FileUploadResult] = Field(description="Детали успешных загрузок")
    failed_uploads: List[FileUploadError] = Field(description="Детали неудачных загрузок")
    
    # Общая информация
    processing_time: float = Field(description="Общее время обработки batch в секундах")
    total_size: int = Field(description="Общий размер загруженных файлов в байтах")
    message: str = Field(default="Batch processing completed")
    timestamp: datetime = Field(default_factory=datetime.now)


class PhotoUploadError(BaseModel):
    """Критическая ошибка при обработке"""
    header: Literal["train"] = Field(description="Тип операции")
    bot_id: int = Field(description="ID бота")
    user_id: int = Field(description="ID пользователя")
    avatar_id: str = Field(description="ID аватара")
    batch_id: Optional[str] = Field(default=None, description="ID batch")
    error: str = Field(description="Описание критической ошибки")
    error_code: str = Field(description="Код ошибки")
    failed_files: List[str] = Field(description="Список ID файлов, которые не удалось обработать")
    timestamp: datetime = Field(default_factory=datetime.now)


class InferencePayloadData(BaseModel):
    """Данные в payload для inference"""
    user_id: int = Field(description="ID пользователя")
    avatar_id: int = Field(description="ID аватара")
    reason: str = Field(description="Причина ошибки", example="ComfyUI: Division by zero")


class InferenceRequest(BaseModel):
    """Запрос на inference (новый формат)"""
    subject: str = Field(description="Тема сообщения", example="ms.inference.prod")
    payload: Dict[str, InferencePayloadData] = Field(description="Полезная нагрузка с данными")
    headers: MessageHeaders = Field(description="Заголовки сообщения")
    
    @field_validator('payload')
    @classmethod
    def validate_payload_structure(cls, v):
        if 'data' not in v:
            raise ValueError('payload must contain "data" key')
        return v
    
    @property
    def data(self) -> InferencePayloadData:
        """Удобный доступ к данным"""
        return self.payload['data'] 