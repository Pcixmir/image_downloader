from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Optional, Literal, List
from datetime import datetime


class BaseRequest(BaseModel):
    chat_id: int


class PhotoUploadRequest(BaseModel):
    """Запрос на загрузку фотографий"""
    header: Literal["inf", "train"] = Field(description="Тип операции: inf или train")
    file_id: List[str] = Field(description="Список ID файлов")
    s3_key: List[str] = Field(description="Список ключей S3 для сохранения")
    bot_id: int = Field(description="ID бота")
    chat_id: int = Field(description="ID чата")
    job_id: int = Field(description="ID задачи")
    
    @field_validator('s3_key')
    @classmethod
    def validate_s3_key_length(cls, v, info):
        if 'file_id' in info.data and len(v) != len(info.data['file_id']):
            raise ValueError('s3_key list must have same length as file_id list')
        return v


class PhotoUploadResult(BaseModel):
    """Результат успешной загрузки фотографий"""
    header: Literal["inf", "train"] = Field(description="Тип операции")
    file_id: List[str] = Field(description="Список успешно загруженных файлов")
    s3_key: List[str] = Field(description="Список ключей S3")
    s3_url: List[str] = Field(description="Список URL загруженных файлов")
    bot_id: int = Field(description="ID бота")
    chat_id: int = Field(description="ID чата")
    job_id: int = Field(description="ID задачи")
    message: str = Field(default="Photos uploaded successfully")


class FileUploadResult(BaseModel):
    """Результат загрузки одного файла"""
    file_id: str                    # ID файла
    s3_key: str                     # Ключ в S3
    s3_url: str                     # URL файла в S3
    file_size: int                  # Размер файла
    upload_time: float              # Время загрузки файла
    success: bool = True
    error_message: Optional[str] = None


class PhotoUploadError(BaseModel):
    """Ошибка при загрузке фотографий"""
    header: Literal["inf", "train"] = Field(description="Тип операции")
    file_id: List[str] = Field(description="Список файлов, которые не удалось загрузить")
    bot_id: int = Field(description="ID бота")
    chat_id: int = Field(description="ID чата")
    job_id: int = Field(description="ID задачи")
    error: str = Field(description="Описание ошибки")
    error_code: str = Field(description="Код ошибки")
    failed_files: List[str] = Field(description="Список ID файлов, которые не удалось загрузить")
    timestamp: datetime = Field(default_factory=datetime.now) 