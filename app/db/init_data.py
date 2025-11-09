# app/db/init_data.py
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.user import User
from app.models.role import Role
from app.core.security import get_password_hash


def _unique_username(db: Session, base: str) -> str:
    """Create a unique username based on a base string."""
    base = (base or "admin").strip() or "admin"
    candidate = base
    i = 1
    while db.query(User).filter_by(username=candidate).first():
        i += 1
        candidate = f"{base}{i}"
    return candidate


def init_base_data():
    db: Session = SessionLocal()
    try:
        # === Seed default roles (idempotent) ===
        role_names = [
            "admin",
            "user",
            "verified",
            "journalist",
            "editor",
            "economist",
            "military_commander",
            "diplomat",
        ]
        for r in role_names:
            role = db.query(Role).filter_by(name=r).first()
            if not role:
                role = Role(name=r)
                db.add(role)
                db.commit()
                db.refresh(role)

        # === Ensure first superuser exists (idempotent) ===
        admin = db.query(User).filter_by(email=settings.FIRST_SUPERUSER_EMAIL).first()
        if not admin:
            admin_role = db.query(Role).filter_by(name="admin").first()

            # Derive a unique username from the email local-part
            email_local = (settings.FIRST_SUPERUSER_EMAIL or "admin").split("@")[0]
            username = _unique_username(db, email_local)

            admin = User(
                email=settings.FIRST_SUPERUSER_EMAIL,
                username=username,
                first_name="System",
                last_name="Admin",
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                is_active=True,
            )
            if admin_role:
                admin.roles.append(admin_role)

            db.add(admin)
            db.commit()
            db.refresh(admin)
    finally:
        db.close()
