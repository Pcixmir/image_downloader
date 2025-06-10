# 📸 Photo Downloader Service

Микросервис для загрузки фотографий из **Telegram** в **S3** через **NATS** очереди сообщений.

## 🎯 Основные возможности

- **Telegram интеграция**: Скачивание файлов по `file_id` через Telegram Bot API
- **Batch обработка**: До 100 фотографий параллельно для тренировки
- **Одиночные фото**: Быстрая обработка для inference
- **S3 загрузка**: Автоматическая организация файлов по структуре
- **NATS messaging**: Асинхронная обработка через очереди
- **Мониторинг**: Детальная статистика и логирование

## 🔄 Архитектура

```
Telegram Bot → NATS Topics → Photo Downloader → S3 Storage
     ↓              ↓              ↓              ↓
  file_id    photo_upload_*   Download &     Organized
             messages         Process        Structure
```

### Процесс обработки:

1. **Получение `file_id`** из Telegram сообщения
2. **Отправка в NATS** topic (`photo_upload_train` или `photo_upload_inf`)
3. **Получение URL** файла через Telegram Bot API (`getFile`)
4. **Скачивание** файла по полученному URL
5. **Загрузка в S3** с метаданными и правильной структурой
6. **Отправка результата** обратно в NATS

### NATS Topics Flow:

## 📋 Описание

Photo Downloader Service - это микросервис, который:
- **Для тренировки (train)**: Получает batch сообщения и обрабатывает множественные фотографии параллельно
- **Для inference (inf)**: Получает запросы на загрузку одиночных фотографий
- Скачивает фотографии по предоставленным file_id
- Загружает их в S3 с разной структурой для train/inference
- Предоставляет детальную статистику обработки
- Отправляет результаты обратно в NATS

## 🚀 Ключевые возможности

### ✨ Разделение по типам операций:
- **Train операции**: Batch обработка до 100 фотографий параллельно
- **Inference операции**: Быстрая загрузка одиночных фотографий
- **Параллельная обработка**: До 5 файлов одновременно для batch (настраивается)

- **Автогенерация S3 ключей**: Если `s3_key` пустой, генерируется уникальный ключ на основе `user_id`, `file_id` и временной метки
- **Детальная статистика**: Индивидуальная информация о каждом файле
- **Обработка ошибок**: Индивидуальные ошибки для каждого файла

## 🏗️ Архитектура

```
HTTP Client → NATS Gateway → NATS → Photo Downloader → S3
                                ↓      
                          ┌─────────────┐
                          │ photo_upload_train │  → Batch Processing (до 100 фото)
                          │ photo_upload_inf   │  → Single Photo (1 фото)
                          └─────────────┘
```

### Структура S3

```
bucket-name/
├── {bot_id}/                       # Тренировочные данные (train)
│   └── {user_id}/
│       └── {avatar_id}/
│           ├── photo1.jpg
│           ├── photo2.jpg
│           └── photo3.jpg
└── uploads/                        # Inference данные (inf)
    └── inf/
        └── {bot_id}/
            └── {user_id}/
                └── {avatar_id}/
                    └── photo.jpg    # Одиночные фото без batch_id
```

**Важно:** 
- **Train** (`header: "train"`): Batch фотографии → `{bot_id}/{user_id}/{avatar_id}/`
- **Inference** (`header: "inf"`): Одиночные фото → `uploads/inf/{bot_id}/{user_id}/{avatar_id}/`

## 🚀 Быстрый старт

### Предварительные требования

- Python 3.11+
- Poetry
- Docker (опционально)
- NATS Server
- S3-совместимое хранилище

### Установка

1. **Клонирование репозитория**
```bash
git clone <repository-url>
cd photo-downloader-service
```

2. **Настройка окружения**
```bash
make setup
# Отредактируйте .env файл с вашими настройками
```

3. **Установка зависимостей**
```bash
make install
```

4. **Запуск**
```bash
make run
```

### Docker

1. **Сборка образа**
```bash
make build
```

2. **Запуск контейнера**
```bash
make docker-run
```

3. **Запуск с docker-compose (включает NATS и MinIO)**
```bash
make compose-up
```

## ⚙️ Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `NATS_URL` | URL NATS сервера | `nats://localhost:4222` |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота | - |
| `TELEGRAM_API_URL` | URL Telegram Bot API | `https://api.telegram.org` |
| `S3_ENDPOINT_URL` | URL S3 endpoint | - |
| `S3_ACCESS_KEY_ID` | S3 Access Key | - |
| `S3_SECRET_ACCESS_KEY` | S3 Secret Key | - |
| `S3_BUCKET_NAME` | Имя S3 bucket | - |
| `S3_REGION` | S3 регион | `us-east-1` |


| `DOWNLOAD_TIMEOUT_SECONDS` | Таймаут загрузки (сек) | `30` |
| `MAX_CONCURRENT_DOWNLOADS` | Макс. параллельных загрузок | `5` |
| `MAX_BATCH_SIZE` | Макс. размер batch (train) | `100` |
| `BATCH_PROCESSING_TIMEOUT` | Таймаут обработки batch (сек) | `300` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

## 📡 API

### NATS Topics

#### Входящие сообщения

**Topic:** `photo_upload_train` - Batch обработка для тренировки

**Схема:** `PhotoUploadRequest`
```json
{
  "header": "train",
  "photos": [
    {
      "file_id": "BAADBAADrwADBREAAWn4gALvKoNaAg",
      "properties":{
        "s3_key": "",
        "file_size": 1024000,
        "width": 1920,
        "height": 1280,
        "face_diagoanl": 360,
        "bboxs": "box list",
        "num_face": 1,
      },
      "status": "ok/error",
      "reason": "NO_FACE/BAD_QUALITY/FACE_TOO_SMALL"
    },
    {
      "file_id": "BAADBAADsAADBREAAQoJBgAB7ioNaAg",
      "properties":{
        "s3_key": "",
        "file_size": 1024000,
        "width": 1920,
        "height": 1280,
        "face_diagoanl": 360,
        "bboxs": "box list",
        "num_face": 1,
      },
      "status": "ok/error",
      "error_details": "NO_FACE/BAD_QUALITY/FACE_TOO_SMALL" 
    }
  ],
  "bot_id": 12345,
  "user_id": 67890,
  "avatar_id": "avatar_abc123",
  "batch_id": "batch_xyz789",
  "priority": 5
}
```

> **Примечание:** Поле `s3_key` может быть пустым (`""`) - в этом случае ключ будет сгенерирован автоматически на основе `user_id`, `file_id` и временной метки в формате `photos/{user_id}/{timestamp}/{file_id}.{ext}`.

**Topic:** `photo_upload_inf` - Одиночное фото для inference

**Схема:** `InferencePhotoRequest`
```json
{
  "header": "inf",
  "photo": {
    "file_id": "BAADBAADrwADBREAAWn4gALvKoNaAg",
    "s3_key": "",
    "file_size": 1024000
  },
  "bot_id": 12345,
  "user_id": 67890,
  "avatar_id": "avatar_abc123",
  "priority": 5
}
```

#### Исходящие сообщения

**Topic:** `photo_upload_result` - Результат batch обработки (train)

**Схема:** `PhotoUploadResult`
```json
{
  "header": "train",
  "bot_id": 12345,
  "user_id": 67890,
  "avatar_id": "avatar_abc123",
  "batch_id": "batch_xyz789",
  "total_files": 2,
  "successful_files": 2,
  "failed_files": 0,
  "successful_uploads": [
    {
      "file_id": "BAADBAADrwADBREAAWn4gALvKoNaAg",
      "s3_key": "12345/67890/avatar_abc123/photo1.jpg",
      "s3_url": "https://bucket.s3.amazonaws.com/12345/67890/avatar_abc123/photo1.jpg",
      "file_size": 1024000,
      "upload_time": 2.5,
      "content_type": "image/jpeg"
    }
  ],
  "failed_uploads": [],
  "processing_time": 5.2,
  "total_size": 3072000,
  "message": "Batch processing completed: 2/2 files successful",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Topic:** `inference_result` - Результат одиночного фото (inference)

**Схема:** `InferencePhotoResult`
```json
{
  "header": "inf",
  "bot_id": 12345,
  "user_id": 67890,
  "avatar_id": "avatar_abc123",
  "upload_result": {
    "file_id": "BAADBAADrwADBREAAWn4gALvKoNaAg",
    "s3_key": "uploads/inf/12345/67890/avatar_abc123/photo.jpg",
    "s3_url": "https://bucket.s3.amazonaws.com/uploads/inf/12345/67890/avatar_abc123/photo.jpg",
    "file_size": 1024000,
    "upload_time": 2.1,
    "content_type": "image/jpeg"
  },
  "processing_time": 2.1,
  "message": "Photo uploaded successfully",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**Topic:** `photo_upload_error` - Ошибки

**Схема:** `PhotoUploadError`
```json
{
  "header": "inf",
  "bot_id": 12345,
  "user_id": 67890,
  "avatar_id": "avatar_abc123",
  "error": "Download failed",
  "error_code": "DOWNLOAD_HTTP_ERROR",
  "failed_files": ["BAADBAADrwADBREAAWn4gALvKoNaAg"],
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 🔧 Коды ошибок

| Код ошибки | Описание |
|------------|----------|

| `INFERENCE_PROCESSING_ERROR` | Ошибка обработки inference фото |
| `TELEGRAM_API_ERROR` | Ошибка при обращении к Telegram Bot API |
| `INVALID_TELEGRAM_URL` | Некорректный URL от Telegram API |


| `DOWNLOAD_HTTP_ERROR` | HTTP ошибка при скачивании |
| `DOWNLOAD_TIMEOUT` | Таймаут при скачивании |
| `S3_UPLOAD_ERROR` | Ошибка загрузки в S3 |
| `UNEXPECTED_ERROR` | Неожиданная ошибка |
| `INTERNAL_ERROR` | Внутренняя ошибка сервиса |

## 🛠️ Использование

### Train операции (Batch)

```bash
# Отправка batch для тренировки (с автогенерацией s3_key)
nats pub photo_upload_train '{
  "header": "train",
  "photos": [
    {"file_id": "photo1_url", "s3_key": ""},
    {"file_id": "photo2_url", "s3_key": ""}
  ],
  "bot_id": 12345,
  "user_id": 67890,
  "avatar_id": "train_avatar_123"
}'

# Отправка batch с кастомными s3_key
nats pub photo_upload_train '{
  "header": "train",
  "photos": [
    {"file_id": "photo1_url", "s3_key": "custom1.jpg"},
    {"file_id": "photo2_url", "s3_key": "custom2.jpg"}
  ],
  "bot_id": 12345,
  "user_id": 67890,
  "avatar_id": "train_avatar_123"
}'
```

### Inference операции (Одиночные фото)

```bash
# Отправка одного фото для inference (с автогенерацией s3_key)
nats pub photo_upload_inf '{
  "header": "inf",
  "photo": {
    "file_id": "photo_url",
    "s3_key": ""
  },
  "bot_id": 12345,
  "user_id": 67890,
  "avatar_id": "inf_avatar_123"
}'
```

## 🛠️ Разработка

### Команды Make

```bash
make help           # Показать все доступные команды
make install        # Установить зависимости
make dev            # Установить dev зависимости
make run            # Запустить приложение
make test           # Запустить тесты
make lint           # Проверить код линтерами
make format         # Отформатировать код
make clean          # Очистить временные файлы
make check          # Полная проверка (lint + test)
```

### Структура проекта

```
photo-downloader-service/
├── app/
│   ├── main.py                 # Основное приложение FastStream
│   ├── schemas/
│   │   └── schemas.py          # Pydantic схемы
│   ├── services/
│   │   ├── s3_service.py       # Сервис для работы с S3
│   │   └── photo_downloader.py # Основная логика загрузки
│   ├── settings/
│   │   └── settings.py         # Настройки приложения
│   └── utils/
│       └── logger.py           # Утилиты логирования
├── pyproject.toml              # Poetry конфигурация
├── Dockerfile                  # Docker образ
├── docker-compose.yml          # Локальная разработка
├── Makefile                    # Команды разработки
├── env.example                 # Пример переменных окружения
└── README.md                   # Документация
```

### Тестирование

```bash
# Запуск всех тестов
make test

# Запуск с покрытием
poetry run pytest --cov=app

# Запуск конкретного теста
poetry run pytest tests/test_photo_downloader.py
```

### Линтинг и форматирование

```bash
# Проверка кода
make lint

# Автоформатирование
make format

# Полная проверка
make check
```

## 🐳 Docker

### Локальная разработка с docker-compose

```bash
# Запуск всех сервисов (NATS, MinIO, Photo Downloader)
make compose-up

# Просмотр логов
make compose-logs

# Остановка
make compose-down
```

### Доступ к сервисам

- **NATS**: `localhost:4222`
- **NATS Monitoring**: `http://localhost:8222`
- **MinIO Console**: `http://localhost:9001` (admin/admin123)
- **MinIO API**: `http://localhost:9000`

## 📊 Мониторинг

### Логирование

Сервис использует `personix-logger` для структурированного логирования:

```python
from app.utils.logger import logger

# Train operations
logger.info("Processing training batch", extra={
    "avatar_id": request.avatar_id,
    "batch_size": len(request.photos)
})

# Inference operations  
logger.info("Processing inference photo", extra={
    "avatar_id": request.avatar_id,
    "file_id": request.photo.file_id
})
```

### Метрики

#### Train операции:
- Количество batch
- Размер batch (количество фото)
- Время обработки batch
- Успешные/неудачные файлы в batch

#### Inference операции:
- Количество одиночных фото
- Время загрузки каждого фото
- Успешные/неудачные загрузки

## 🔧 Устранение неполадок

### Частые проблемы

1. **Ошибка подключения к NATS**
   ```
   Проверьте NATS_URL в .env файле
   Убедитесь, что NATS сервер запущен
   ```

2. **Неправильная структура S3**
   ```
   Train: {bot_id}/{user_id}/{avatar_id}/filename.jpg
   Inference: uploads/inf/{bot_id}/{user_id}/{avatar_id}/filename.jpg
   ```

3. **Проблемы с типами операций**
   ```
   Используйте photo_upload_train для batch (train)
   Используйте photo_upload_inf для одиночных фото (inf)
   ```