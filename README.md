# Photo Downloader Service

Микросервис для загрузки фотографий в S3 через NATS.

## 📋 Описание

Photo Downloader Service - это микросервис, который:
- Получает сообщения из NATS по теме `photo_upload`
- Скачивает фотографии по предоставленным file_id
- Загружает их в S3 с организованной структурой папок
- Отправляет результаты обратно в NATS

## 🏗️ Архитектура

```
HTTP Client → NATS Gateway → NATS → Photo Downloader → S3
```

### Структура S3

```
uploads/
├── inf/                    # Inference операции
│   └── {bot_id}/
│       └── {chat_id}/
│           └── {job_id}/
│               ├── photo1.jpg
│               └── photo2.jpg
└── train/                  # Training операции
    └── {bot_id}/
        └── {chat_id}/
            └── {job_id}/
                ├── photo1.jpg
                └── photo2.jpg
```

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
| `S3_ENDPOINT_URL` | URL S3 endpoint | - |
| `S3_ACCESS_KEY_ID` | S3 Access Key | - |
| `S3_SECRET_ACCESS_KEY` | S3 Secret Key | - |
| `S3_BUCKET_NAME` | Имя S3 bucket | - |
| `S3_REGION` | S3 регион | `us-east-1` |
| `MAX_FILE_SIZE_MB` | Максимальный размер файла (MB) | `10` |
| `DOWNLOAD_TIMEOUT_SECONDS` | Таймаут загрузки (сек) | `30` |
| `LOG_LEVEL` | Уровень логирования | `INFO` |

## 📡 API

### NATS Topics

#### Входящие сообщения

**Topic:** `photo_upload`

**Схема:** `PhotoUploadRequest`
```json
{
  "header": "inf",                    // "inf" | "train"
  "file_id": ["photo1", "photo2"],    // Список ID файлов
  "s3_key": ["path1.jpg", "path2.jpg"], // Список ключей S3
  "bot_id": 12345,                    // ID бота
  "chat_id": 67890,                   // ID чата
  "job_id": 123                       // ID задачи
}
```

#### Исходящие сообщения

**Topic:** `photo_upload_result` (успех)

**Схема:** `PhotoUploadResult`
```json
{
  "header": "inf",
  "file_id": ["photo1", "photo2"],
  "s3_key": ["uploads/inf/12345/67890/123/path1.jpg"],
  "s3_url": ["https://bucket.s3.amazonaws.com/uploads/inf/12345/67890/123/path1.jpg"],
  "bot_id": 12345,
  "chat_id": 67890,
  "job_id": 123,
  "message": "Successfully uploaded 2 photos"
}
```

**Topic:** `photo_upload_error` (ошибка)

**Схема:** `PhotoUploadError`
```json
{
  "header": "inf",
  "file_id": ["photo1"],
  "bot_id": 12345,
  "chat_id": 67890,
  "job_id": 123,
  "error": "File size exceeds maximum",
  "error_code": "VALIDATION_ERROR"
}
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

logger.info("Processing photo upload", extra={
    "job_id": request.job_id,
    "file_count": len(request.file_id)
})
```

### Метрики

- Количество обработанных файлов
- Время загрузки
- Ошибки загрузки
- Размеры файлов

## 🔧 Устранение неполадок

### Частые проблемы

1. **Ошибка подключения к NATS**
   ```
   Проверьте NATS_URL в .env файле
   Убедитесь, что NATS сервер запущен
   ```

2. **Ошибка доступа к S3**
   ```
   Проверьте S3 credentials в .env
   Убедитесь, что bucket существует
   Проверьте права доступа
   ```

3. **Превышение размера файла**
   ```
   Увеличьте MAX_FILE_SIZE_MB в настройках
   Проверьте размер загружаемых файлов
   ```

### Логи

```bash
# Docker логи
make docker-logs

# docker-compose логи
make compose-logs

# Локальные логи
tail -f logs/photo-downloader.log
```

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте feature ветку (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. Отправьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📄 Лицензия

Этот проект лицензирован под MIT License - см. файл [LICENSE](LICENSE) для деталей.

## 📞 Поддержка

Если у вас есть вопросы или проблемы:

1. Проверьте [Issues](../../issues)
2. Создайте новый Issue с подробным описанием
3. Обратитесь к команде разработки 