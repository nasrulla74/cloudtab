from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRead(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
