from fastapi import APIRouter, Depends, HTTPException
from fastapi import status
from src.db.models.user import User
from src.db.models.folder import Folder
from src.db.session import AsyncSession
from pydantic import UUID4
from src.endpoints.deps import get_db, get_user_id
from src.crud.crud_user import user as crud_user
from src.crud.crud_folder import folder as crud_folder
router = APIRouter()

@router.post(
    "",
    response_model=User,
    summary="Create a user.",
    status_code=201,
)
async def create_user(
    *,
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
):
    """Create a user. This will read the user ID from the JWT token or use the pre-defined user_id if running without authentication."""

    # Check if user already exists
    user = await crud_user.get(async_session, id=user_id)
    if user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    else:
        # Create user tables
        await crud_user.create_user_data_tables(async_session, user_id=user_id)
        try:
            # Create user
            user = await crud_user.create(async_session, obj_in=User(id=user_id))
            # Create home folder
            folder = Folder(name="home", user_id=user_id)
            await crud_folder.create(
                async_session,
                obj_in=folder,
            )
            return user
        except Exception as e:
            await crud_user.delete_user_data_tables(async_session, user_id)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "",
    response_model=User,
    summary="Get a user.",
    status_code=200,
)
async def get_user(
    *,
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
):
    """Get a user. This will read the user ID saved in the GOAT DB."""
    user = await crud_user.get(async_session, id=user_id)
    if user:
        return user
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

@router.delete(
    "",
    response_model=None,
    summary="Delete a user and all of the related contents.",
    status_code=204,
)
async def delete_user(
    *,
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
):
    """Delete a user and all of the related contents. This will read the user ID from the JWT token or use the pre-defined user_id if running without authentication."""
    user = await crud_user.get(async_session, id=user_id)

    if user:
        await crud_user.remove(async_session, id=user_id)
        # Delete user tables
        await crud_user.delete_user_data_tables(async_session, user_id=user.id)
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return
