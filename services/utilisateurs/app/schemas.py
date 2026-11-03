"""Schémas Pydantic du service Utilisateurs."""

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,128}$")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(description="Minimum 8 caractères, lettres + chiffres")
    full_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not _PASSWORD_RE.match(v):
            raise ValueError("Mot de passe trop faible : minimum 8 caractères, lettres et chiffres")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: str


class UserRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    phone: str | None
    role: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    current_password: str | None = None
    new_password: str | None = Field(default=None)

    @field_validator("new_password")
    @classmethod
    def strong_new_password(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _PASSWORD_RE.match(v):
            raise ValueError("Mot de passe trop faible : minimum 8 caractères, lettres et chiffres")
        return v


class UserAdminRow(UserRead):
    is_active: bool
