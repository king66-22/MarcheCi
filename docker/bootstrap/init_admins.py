"""Amorçage des comptes nécessaires au bon fonctionnement de la plateforme.

Exécuté comme service one-shot de compose (image `utilisateurs`) APRÈS les
migrations. Crée :
  - le compte ADMIN de démonstration (env ADMIN_EMAIL / ADMIN_PASSWORD),
  - le compte système svc.commandes (rôle ADMIN) utilisé par le service
    commandes pour les appels inter-services (décision doc §04.3 : JWT).

Idempotent : ne modifie rien si les comptes existent déjà.
"""

import os
import sys

sys.path.insert(0, "/app")  # WORKDIR de l'image utilisateurs

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402


def ensure(db, email: str, password: str, full_name: str, role: str) -> None:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None:
        print(f"[bootstrap] {email} existe déjà (rôle {user.role}) — inchangé")
        return
    db.add(
        User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
        )
    )
    db.commit()
    print(f"[bootstrap] {email} créé (rôle {role})")


def main() -> None:
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]
    svc_email = os.environ["SVC_COMMANDES_EMAIL"]
    svc_password = os.environ["SVC_COMMANDES_PASSWORD"]

    if len(admin_password) < 8 or len(svc_password) < 8:
        print("[bootstrap] Mots de passe < 8 caractères : motifs de démo refusés")
        sys.exit(1)

    db = SessionLocal()
    try:
        ensure(db, svc_email, svc_password, "Service Commandes", "ADMIN")
        ensure(db, admin_email, admin_password, "Administration MarchéCI", "ADMIN")
    finally:
        db.close()
    print("[bootstrap] terminé")


if __name__ == "__main__":
    main()
