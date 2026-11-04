"""Pré-remplissage direct de la base Utilisateurs pour les tests d'intégration.

Exécuté avec cwd = services/utilisateurs et DATABASE_URL pointant vers la base
de test : les inserts passent par l'ORM/le moteur du service (argon2 correct,
schéma correct).
"""

from __future__ import annotations

import os
import sys

# cwd = services/utilisateurs → import du package `app` du service
sys.path.insert(0, os.getcwd())

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import User
from argon2 import PasswordHasher

ACCOUNTS = [
    # (email, mot de passe, nom, téléphone, rôle) — la politique ≥8 avec lettres/chiffres est respectée
    ("admin@example.ci", "AdminFort123", "Admin MarchéCI", "0700000001", "ADMIN"),
    ("client@example.ci", "Client1234", "Client Test CI", "0700000002", "CLIENT"),
    ("svc.commandes@example.ci", "SysCmd123!", "Compte système Commandes", "0700000003", "ADMIN"),
]


def main() -> None:
    ph = PasswordHasher()
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for email, password, full_name, phone, role in ACCOUNTS:
            exists = db.scalar(select(User.id).where(User.email == email))
            if exists is not None:
                print(f"existant : {email}")
                continue
            db.add(
                User(
                    email=email,
                    password_hash=ph.hash(password),
                    full_name=full_name,
                    phone=phone,
                    role=role,
                    is_active=True,
                )
            )
            print(f"inséré : {email} ({role})")
        db.commit()


if __name__ == "__main__":
    main()
