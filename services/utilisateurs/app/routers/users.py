"""Endpoints auth + profil + administration."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import (
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    RoleUpdate,
    TokenResponse,
    UserAdminRow,
    UserRead,
)
from ..security import (
    create_access_token,
    get_current_user,
    get_rate_limiter,
    hash_password,
    require_admin,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()
auth_router = APIRouter(prefix="/auth", tags=["auth"])

DB = Annotated[Session, Depends(get_db)]


@auth_router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: DB):
    """Inscription d'un compte CLIENT ou COMMERCANT. ADMIN reste réservé à l'amorçage."""
    if db.scalar(select(User.id).where(User.email == data.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cet email")
    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        full_name=data.full_name.strip(),
        phone=data.phone,
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("event", extra={"event": "user_registered", "user_id": user.id})
    return user


@auth_router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DB):
    """Connexion. Message d'échec volontairement générique (pas d'énumération de comptes)."""
    limiter = get_rate_limiter()
    key = data.email.lower()
    if limiter.is_blocked(key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Trop de tentatives. Réessayez dans {get_rate_limiter().max_failures//60 or 5} minutes",
        )

    user = db.scalar(select(User).where(User.email == key))
    if user is None or not verify_password(data.password, user.password_hash):
        limiter.register_failure(key)
        logger.info("event", extra={"event": "login_failed", "detail": key})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Compte désactivé")

    limiter.reset(key)
    token, expires_in = create_access_token(user)
    logger.info("event", extra={"event": "login_success", "user_id": user.id})
    return TokenResponse(access_token=token, expires_in=expires_in, role=user.role)


@router.get("/users/me", response_model=UserRead)
def me(user: Annotated[User, Depends(get_current_user)]):
    """Profil courant. Le hash de mot de passe n'est jamais retourné."""
    return user


@router.put("/users/me", response_model=UserRead)
def update_profile(
    data: ProfileUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: DB,
):
    if data.full_name is not None:
        user.full_name = data.full_name.strip()
    if data.phone is not None:
        user.phone = data.phone
    if data.new_password is not None:
        if data.current_password is None or not verify_password(data.current_password, user.password_hash):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Mot de passe actuel incorrect")
        user.password_hash = hash_password(data.new_password)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserAdminRow])
def list_users(
    _admin: Annotated[User, Depends(require_admin)],
    db: DB,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    rows = db.scalars(
        select(User).order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return rows


@router.patch("/users/{user_id}/role", response_model=UserAdminRow)
def update_role(
    user_id: int,
    data: RoleUpdate,
    _admin: Annotated[User, Depends(require_admin)],
    db: DB,
):
    """Promeut un client en commerçant (ou l'inverse). Le rôle ADMIN n'est jamais modifiable ici."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable")
    if user.role == "ADMIN":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Le rôle ADMIN est réservé au script d'amorçage et ne peut pas être modifié",
        )
    # L'appelant est nécessairement ADMIN (require_admin), donc jamais la cible :
    # aucune auto-modification de rôle n'est possible.
    user.role = data.role
    db.commit()
    db.refresh(user)
    logger.info("event", extra={"event": "user_role_updated", "user_id": user.id, "role": user.role})
    return user
