from fastapi import APIRouter
from src.schemas.User_models import UserResponse
from src.services.local_user_service import get_local_user

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def get_current_user():
    result = get_local_user()

    return UserResponse(
        id=result["id"],
        email=result["email"],
        name=result["name"],
        unsubscribe_public_key=result.get("unsubscribe_public_key"),
    )
