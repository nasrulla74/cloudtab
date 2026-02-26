from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.services.auth_service import authenticate_user, create_tokens, create_user, get_user_by_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/setup")
async def setup_status(db: AsyncSession = Depends(get_db)):
    """Returns whether first-time setup is required (no users exist)."""
    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar()
    return {"setup_required": count == 0}


@router.post("/setup", response_model=TokenResponse)
async def setup(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Create the first admin user. Disabled once any user exists."""
    result = await db.execute(select(func.count()).select_from(User))
    if result.scalar() > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup already completed",
        )
    user = await create_user(db, body.email, body.password)
    return create_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return create_tokens(user)


@router.post("/register", response_model=TokenResponse)
async def register(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    existing = await get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = await create_user(db, body.email, body.password)
    return create_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return create_tokens(user)
