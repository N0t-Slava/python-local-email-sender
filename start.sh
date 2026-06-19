#!/usr/bin/env bash
set -e

mkdir -p logs

echo "=== Запуск Redis (Valkey) ==="
sudo sysctl -w vm.overcommit_memory=1 >/dev/null
sudo systemctl enable --now valkey
sudo systemctl is-active --quiet valkey && echo "Valkey запущен" || echo "Valkey НЕ запущен"

echo "=== Запуск RabbitMQ ==="
sudo systemctl enable --now rabbitmq
sudo systemctl is-active --quiet rabbitmq && echo "RabbitMQ запущен" || echo "RabbitMQ НЕ запущен"

echo "=== Запуск Mailhog ==="
MAILHOG_PID=$(pgrep -f "mailhog" || true)
if [ -z "$MAILHOG_PID" ]; then
    nohup mailhog > logs/mailhog.log 2>&1 &
    echo "Mailhog запущен"
else
    echo "Mailhog уже запущен (PID $MAILHOG_PID)"
fi

# --- Активация виртуального окружения ---
if command -v poetry &> /dev/null; then
    echo "Activating poetry environment..."
    source "$(poetry env info --path)/bin/activate"
else
    echo "POetry not installed"
    exit 1
fi


echo "=== Запуск веб-сервиса (Uvicorn) ==="
UVICORN_PID=$(pgrep -f "uvicorn src.main:app" || true)
if [ -z "$UVICORN_PID" ]; then
    nohup uvicorn src.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        > logs/web.log 2>&1 &
    echo "Uvicorn запущен"
else
    echo "Uvicorn уже работает (PID $UVICORN_PID)"
fi

echo "=== Запуск Celery Worker ==="
CELERY_PID=$(pgrep -f "celery -A src.tasks.celery_app worker" || true)
if [ -z "$CELERY_PID" ]; then
    nohup celery -A src.tasks.celery_app worker \
        --loglevel=info \
        --concurrency=4 \
        > logs/worker.log 2>&1 &
    echo "Celery Worker запущен"
else
    echo "Celery Worker уже работает (PID $CELERY_PID)"
fi

echo "=== Запуск Celery Beat ==="
CELERY_BEAT_PID=$(pgrep -f "celery -A src.tasks.celery_app beat" || true)
if [ -z "$CELERY_BEAT_PID" ]; then
    nohup celery -A src.tasks.celery_app beat \
        --loglevel=info \
        > logs/beat.log 2>&1 &
    echo "Celery Beat запущен"
else
    echo "Celery Beat уже работает (PID $CELERY_BEAT_PID)"
fi

echo "Готово. Логи: logs/"
