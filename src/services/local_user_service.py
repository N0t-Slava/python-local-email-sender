from src.configs.config import (
    LOCAL_USER_EMAIL,
    LOCAL_USER_ID,
    LOCAL_USER_NAME,
    LOCAL_USER_UNSUBSCRIBE_PUBLIC_KEY,
)


def get_local_user():
    return {
        "authorization": True,
        "id": LOCAL_USER_ID,
        "email": LOCAL_USER_EMAIL,
        "name": LOCAL_USER_NAME,
        "unsubscribe_public_key": LOCAL_USER_UNSUBSCRIBE_PUBLIC_KEY,
    }
