#!/bin/bash

# Photo Downloader Service Release Script
set -e

# Переменные
SERVICE_NAME="photo-downloader-service"
REGISTRY="cr.yandex/crp9ftr22d26age3hulg"
VERSION=$(cat VERSION)
COMMIT_HASH=$(git rev-parse --short HEAD)

echo "🚀 Starting release for $SERVICE_NAME v$VERSION"

# Проверяем, что мы в правильной директории
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Run this script from the service root directory."
    exit 1
fi

# Проверяем, что все изменения зафиксированы
if [ -n "$(git status --porcelain)" ]; then
    echo "❌ Error: There are uncommitted changes. Please commit all changes before release."
    exit 1
fi

# Проверяем зависимости
echo "📦 Installing dependencies..."
poetry install

# Запускаем тесты
echo "🧪 Running tests..."
poetry run pytest

# Проверяем код
echo "🔍 Running linters..."
poetry run flake8 app/
poetry run mypy app/

# Форматируем код
echo "✨ Formatting code..."
poetry run black app/
poetry run isort app/

# Собираем Docker образ
echo "🐳 Building Docker image..."
docker build -t $SERVICE_NAME:$VERSION .
docker build -t $SERVICE_NAME:latest .

# Тегируем для registry
docker tag $SERVICE_NAME:$VERSION $REGISTRY/$SERVICE_NAME:$VERSION
docker tag $SERVICE_NAME:$VERSION $REGISTRY/$SERVICE_NAME:$COMMIT_HASH
docker tag $SERVICE_NAME:latest $REGISTRY/$SERVICE_NAME:latest

# Пушим в registry
echo "📤 Pushing to registry..."
docker push $REGISTRY/$SERVICE_NAME:$VERSION
docker push $REGISTRY/$SERVICE_NAME:$COMMIT_HASH
docker push $REGISTRY/$SERVICE_NAME:latest

# Создаем git тег
echo "🏷️ Creating git tag..."
git tag -a "v$VERSION" -m "Release version $VERSION"
git push origin "v$VERSION"

echo "✅ Release completed successfully!"
echo "📋 Summary:"
echo "   Service: $SERVICE_NAME"
echo "   Version: $VERSION"
echo "   Commit: $COMMIT_HASH"
echo "   Registry: $REGISTRY/$SERVICE_NAME:$VERSION"
echo ""
echo "🔗 Docker images:"
echo "   docker pull $REGISTRY/$SERVICE_NAME:$VERSION"
echo "   docker pull $REGISTRY/$SERVICE_NAME:latest" 