#!/usr/bin/env bash
set -e

echo "=== Остановка Uvicorn ==="
pkill -f "uvicorn src.main:app" && echo "Uvicorn остановлен" || echo "Uvicorn не запущен"

echo "=== Остановка Celery Worker ==="
pkill -f "celery -A src.tasks.celery_app worker" && echo "Celery остановлен" || echo "Celery не запущен"

echo "=== Остановка Celery Beat ==="
pkill -f "celery -A src.tasks.celery_app beat" && echo "Celery Beat остановлен" || echo "Celery Beat не запущен"

echo "=== Остановка MailHog ==="
pkill -f "mailhog" && echo "MailHog остановлен" || echo "MailHog не запущен"

echo "=== Остановка RabbitMQ ==="
sudo systemctl stop rabbitmq
sudo systemctl is-active --quiet rabbitmq \
    && echo "RabbitMQ всё ещё работает" \
    || echo "RabbitMQ остановлен"

echo "=== Остановка Valkey ==="
sudo systemctl stop valkey
sudo systemctl is-active --quiet valkey \
    && echo "Valkey всё ещё работает" \
    || echo "Valkey остановлен"

echo "Готово"
