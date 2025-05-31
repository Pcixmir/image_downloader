# Photo Downloader Service Makefile

.PHONY: help install dev test lint format clean build run docker-build docker-run docker-stop

# Переменные
DOCKER_IMAGE_NAME = photo-downloader-service
DOCKER_CONTAINER_NAME = photo-downloader
PYTHON_VERSION = 3.11

help: ## Показать справку
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости
	poetry install

dev: ## Установить зависимости для разработки
	poetry install --with dev

test: ## Запустить тесты
	poetry run pytest

lint: ## Проверить код линтерами
	poetry run flake8 app/
	poetry run mypy app/

format: ## Отформатировать код
	poetry run black app/
	poetry run isort app/

clean: ## Очистить временные файлы
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

run: ## Запустить приложение локально
	poetry run python -m app.main

build: ## Собрать Docker образ
	docker build -t $(DOCKER_IMAGE_NAME) .

docker-run: ## Запустить в Docker
	docker run -d \
		--name $(DOCKER_CONTAINER_NAME) \
		--env-file .env \
		-p 8000:8000 \
		$(DOCKER_IMAGE_NAME)

docker-stop: ## Остановить Docker контейнер
	docker stop $(DOCKER_CONTAINER_NAME) || true
	docker rm $(DOCKER_CONTAINER_NAME) || true

docker-logs: ## Показать логи Docker контейнера
	docker logs -f $(DOCKER_CONTAINER_NAME)

compose-up: ## Запустить с docker-compose
	docker-compose up -d

compose-down: ## Остановить docker-compose
	docker-compose down

compose-logs: ## Показать логи docker-compose
	docker-compose logs -f

setup: ## Первоначальная настройка проекта
	cp env.example .env
	@echo "Отредактируйте файл .env с вашими настройками"

check: lint test ## Полная проверка кода 