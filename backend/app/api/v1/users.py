"""AnalytIQ API V1 - Users endpoint."""

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.auth import UserResponse

router = APIRouter()


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get authenticated user ownership profile",
)
async def get_user_me(
    current_user: CurrentUser,
) -> UserResponse:
    """Return profile of currently authenticated user for ownership verification."""
    return UserResponse.model_validate(current_user)
