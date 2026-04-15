import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    invite_code: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    created_at: datetime
    tg_id: int | None = None
    first_name: str | None = None
    birthday: date | None = None
    is_volkov: bool = False
    gender: Literal["male", "female"] | None = None
    notifications_enabled: bool = True

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    first_name: str | None = Field(default=None, max_length=50)
    birthday: date | None = None
    is_volkov: bool | None = None
    gender: Literal["male", "female"] | None = None
    notifications_enabled: bool | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class TelegramLoginRequest(BaseModel):
    tg_id: int


class TokenResponse(BaseModel):
    access_token: str


class NotifiableUserResponse(BaseModel):
    tg_id: int
    first_name: str | None = None
    username: str

    model_config = {"from_attributes": True}
