from typing import Annotated

from fastapi import Depends
from personix_logger.abstract import PersonixLogger, PersonixLogAggregator
from personix_logger.impl import YandexLoggerImpl, YandexLogAggregatorImpl
import logging
import sys
from personix_logger import get_logger
from app.settings.settings import settings

logger_aggregator = YandexLogAggregatorImpl()

yandex_logger = YandexLoggerImpl(aggregator=logger_aggregator, producer_log_tag="photo-downloader")


def get_logger() -> PersonixLogger:
    return yandex_logger


def get_logger_aggregator() -> PersonixLogAggregator:
    return logger_aggregator


Logger = Annotated[YandexLoggerImpl, Depends(get_logger)]


def setup_logger(name: str = "photo-downloader") -> logging.Logger:
    """Настройка логгера для приложения"""
    logger = logging.getLogger(name)
    
    # Устанавливаем уровень логирования
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Проверяем, есть ли уже обработчики
    if not logger.handlers:
        # Создаем обработчик для вывода в консоль
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)
        
        # Создаем форматтер
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        
        # Добавляем обработчик к логгеру
        logger.addHandler(handler)
    
    return logger


# Глобальный логгер для приложения
logger = setup_logger() 