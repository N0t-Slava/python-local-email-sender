import base64
import json
from urllib.parse import urlparse

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from src.configs.config import SNS_SES_TOPIC_ARN


SNS_SIGNATURE_FIELDS = {
    "Notification": ["Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"],
    "SubscriptionConfirmation": ["Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"],
    "UnsubscribeConfirmation": ["Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"],
}

def parse_sns_message(raw_body: bytes) -> dict:
    return json.loads(raw_body.decode("utf-8"))


def get_sns_type(sns_message: dict) -> str | None:
    return sns_message.get("Type")


def parse_ses_message_from_sns(sns_message: dict) -> dict:
    message = sns_message.get("Message")
    if not message:
        return {}

    return json.loads(message)


def _validate_signing_cert_url(cert_url: str):
    parsed = urlparse(cert_url or "")
    hostname = parsed.hostname or ""

    return (
        parsed.scheme == "https"
        and hostname.startswith("sns.")
        and hostname.endswith(".amazonaws.com")
        and parsed.path.endswith(".pem")
    )


def _build_canonical_message(sns_message: dict):
    sns_type = get_sns_type(sns_message)
    fields = SNS_SIGNATURE_FIELDS.get(sns_type)
    if not fields:
        return None

    parts = []
    for field in fields:
        value = sns_message.get(field)
        if value is None:
            continue
        parts.append(f"{field}\n{value}\n")

    return "".join(parts).encode("utf-8")


def verify_sns_message(sns_message: dict):
    if SNS_SES_TOPIC_ARN and sns_message.get("TopicArn") != SNS_SES_TOPIC_ARN:
        return False

    cert_url = sns_message.get("SigningCertURL")
    if not _validate_signing_cert_url(cert_url):
        return False

    canonical_message = _build_canonical_message(sns_message)
    if not canonical_message:
        return False

    signature = sns_message.get("Signature")
    if not signature:
        return False

    response = requests.get(cert_url, timeout=10)
    response.raise_for_status()

    certificate = x509.load_pem_x509_certificate(response.content)
    public_key = certificate.public_key()

    signature_version = sns_message.get("SignatureVersion")
    if signature_version == "1":
        digest = hashes.SHA1()
    elif signature_version == "2":
        digest = hashes.SHA256()
    else:
        return False

    try:
        public_key.verify(
            base64.b64decode(signature),
            canonical_message,
            padding.PKCS1v15(),
            digest,
        )
        return True
    except Exception:
        return False


def confirm_sns_subscription(sns_message: dict):
    subscribe_url = sns_message.get("SubscribeURL")
    if not subscribe_url:
        return {"status": "missing_subscribe_url"}

    response = requests.get(subscribe_url, timeout=10)
    response.raise_for_status()

    return {"status": "confirmed"}
