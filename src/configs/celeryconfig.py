from celery import Celery
from kombu import Exchange, Queue
from src.configs.config import (
    CAMPAIGN_DEFAULT_QUEUE,
    CAMPAIGN_HIGH_QUEUE,
    CAMPAIGN_LOW_QUEUE,
    CELERY_BACKEND,
    MAINTENANCE_QUEUE,
    RABBITMQ_URL,
    SENDING_RECOVERY_INTERVAL_SECONDS,
    SUPPRESSION_SYNC_INTERVAL_SECONDS,
    WEBHOOKS_QUEUE,
)
broker_url = RABBITMQ_URL
result_backend = CELERY_BACKEND

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

task_acks_late = True
worker_prefetch_multiplier = 1
task_default_queue = CAMPAIGN_DEFAULT_QUEUE
task_default_exchange = "tasks"
task_default_exchange_type = "direct"
task_default_routing_key = CAMPAIGN_DEFAULT_QUEUE

task_queues = (
    Queue(CAMPAIGN_HIGH_QUEUE, Exchange("tasks"), routing_key=CAMPAIGN_HIGH_QUEUE, queue_arguments={"x-max-priority": 10}),
    Queue(CAMPAIGN_DEFAULT_QUEUE, Exchange("tasks"), routing_key=CAMPAIGN_DEFAULT_QUEUE, queue_arguments={"x-max-priority": 10}),
    Queue(CAMPAIGN_LOW_QUEUE, Exchange("tasks"), routing_key=CAMPAIGN_LOW_QUEUE, queue_arguments={"x-max-priority": 10}),
    Queue(WEBHOOKS_QUEUE, Exchange("tasks"), routing_key=WEBHOOKS_QUEUE),
    Queue(MAINTENANCE_QUEUE, Exchange("tasks"), routing_key=MAINTENANCE_QUEUE),
)

task_routes = {
    "src.tasks.send_campaign": {"queue": CAMPAIGN_DEFAULT_QUEUE, "routing_key": CAMPAIGN_DEFAULT_QUEUE},
    "src.tasks.send_campaign_worker": {"queue": CAMPAIGN_DEFAULT_QUEUE, "routing_key": CAMPAIGN_DEFAULT_QUEUE},
    "src.tasks.start_scheduled_campaign": {"queue": CAMPAIGN_DEFAULT_QUEUE, "routing_key": CAMPAIGN_DEFAULT_QUEUE},
    "src.tasks.record_recipient_result_task": {"queue": CAMPAIGN_DEFAULT_QUEUE, "routing_key": CAMPAIGN_DEFAULT_QUEUE},
    "src.tasks.process_ses_notification": {"queue": WEBHOOKS_QUEUE, "routing_key": WEBHOOKS_QUEUE},
    "src.tasks.recover_stale_sending_recipients": {"queue": MAINTENANCE_QUEUE, "routing_key": MAINTENANCE_QUEUE},
    "src.tasks.sync_ses_suppression_list": {"queue": MAINTENANCE_QUEUE, "routing_key": MAINTENANCE_QUEUE},
}


task_annotations = {
    "*": {"rate_limit": None}
}

beat_schedule = {
    "recover-stale-sending-recipients": {
        "task": "src.tasks.recover_stale_sending_recipients",
        "schedule": SENDING_RECOVERY_INTERVAL_SECONDS,
    },
    "sync-ses-suppression-list": {
        "task": "src.tasks.sync_ses_suppression_list",
        "schedule": SUPPRESSION_SYNC_INTERVAL_SECONDS,
    }
}

celery_app = Celery(
    "worker",
    broker=RABBITMQ_URL,
    backend=CELERY_BACKEND,
)
