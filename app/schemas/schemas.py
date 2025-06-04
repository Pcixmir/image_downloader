from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, List
from datetime import datetime


class PhotoFile(BaseModel):
    """Информация об одном файле фотографии"""
    file_id: str = Field(description="ID файла в Telegram")
    s3_key: Optional[str] = Field(default="", description="Ключ для сохранения в S3 (может быть пустым - тогда генерируется автоматически)")
    original_filename: Optional[str] = Field(default=None, description="Оригинальное имя файла")
    file_size: Optional[int] = Field(default=None, description="Размер файла в байтах")


class FileUploadResult(BaseModel):
    """Результат загрузки одного файла"""
    file_id: str = Field(description="ID файла")
    s3_key: str = Field(description="Ключ в S3")
    s3_url: str = Field(description="URL файла в S3")
    original_filename: Optional[str] = Field(default=None, description="Оригинальное имя файла")
    file_size: int = Field(description="Размер файла в байтах")
    upload_time: float = Field(description="Время загрузки файла в секундах")
    content_type: str = Field(default="image/jpeg", description="MIME тип файла")


class FileUploadError(BaseModel):
    """Ошибка загрузки одного файла"""
    file_id: str = Field(description="ID файла с ошибкой")
    s3_key: str = Field(description="Предполагаемый ключ в S3")
    error_message: str = Field(description="Описание ошибки")
    error_code: str = Field(description="Код ошибки")
    timestamp: datetime = Field(default_factory=datetime.now)


class PhotoUploadRequest(BaseModel):
    """Запрос на batch загрузку фотографий (для train)"""
    header: Literal["train"] = Field(description="Тип операции: train")
    photos: List[PhotoFile] = Field(description="Batch фотографий для загрузки", min_length=1, max_length=100)
    bot_id: int = Field(description="ID бота")
    user_id: int = Field(description="ID пользователя")
    job_id: str = Field(description="ID задачи")
    batch_id: Optional[str] = Field(default=None, description="ID batch для группировки")
    priority: Optional[int] = Field(default=0, description="Приоритет обработки (0-10)")
    
    @field_validator('photos')
    @classmethod
    def validate_photos_batch(cls, v):
        if not v:
            raise ValueError('photos list cannot be empty')
        
        # Проверяем уникальность file_id
        file_ids = [photo.file_id for photo in v]
        if len(file_ids) != len(set(file_ids)):
            raise ValueError('file_id must be unique within batch')
        
        # Проверяем уникальность s3_key только для непустых значений
        s3_keys = [photo.s3_key for photo in v if photo.s3_key and photo.s3_key.strip()]
        if s3_keys and len(s3_keys) != len(set(s3_keys)):
            raise ValueError('s3_key must be unique within batch (excluding empty values)')
        
        return v


class InferencePhotoRequest(BaseModel):
    """Запрос на загрузку одного фото для inference"""
    header: Literal["inf"] = Field(description="Тип операции: inf")
    photo: PhotoFile = Field(description="Фото для inference")
    bot_id: int = Field(description="ID бота")
    user_id: int = Field(description="ID пользователя")
    job_id: str = Field(description="ID задачи")
    priority: Optional[int] = Field(default=0, description="Приоритет обработки (0-10)")


class PhotoUploadResult(BaseModel):
    """Результат успешной batch загрузки фотографий (для train)"""
    header: Literal["train"] = Field(description="Тип операции")
    bot_id: int = Field(description="ID бота")
    user_id: int = Field(description="ID пользователя")
    job_id: str = Field(description="ID задачи")
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


class InferencePhotoResult(BaseModel):
    """Результат успешной загрузки одного фото для inference"""
    header: Literal["inf"] = Field(description="Тип операции")
    bot_id: int = Field(description="ID бота")
    user_id: int = Field(description="ID пользователя")
    job_id: str = Field(description="ID задачи")
    
    # Детали загруженного файла
    upload_result: FileUploadResult = Field(description="Детали загрузки")
    
    # Общая информация
    processing_time: float = Field(description="Время обработки в секундах")
    message: str = Field(default="Photo uploaded successfully")
    timestamp: datetime = Field(default_factory=datetime.now)


class PhotoUploadError(BaseModel):
    """Критическая ошибка при обработке"""
    header: Literal["train", "inf"] = Field(description="Тип операции")
    bot_id: int = Field(description="ID бота")
    user_id: int = Field(description="ID пользователя")
    job_id: str = Field(description="ID задачи")
    batch_id: Optional[str] = Field(default=None, description="ID batch")
    error: str = Field(description="Описание критической ошибки")
    error_code: str = Field(description="Код ошибки")
    failed_files: List[str] = Field(description="Список ID файлов, которые не удалось обработать")
    timestamp: datetime = Field(default_factory=datetime.now) 