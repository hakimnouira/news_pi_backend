from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.user import User
from app.models.role import Role
from app.core.security import get_password_hash


def init_base_data():
    db: Session = SessionLocal()
    try:
        # Ensure roles exist
        for r in ("admin", "user"):
            role = db.query(Role).filter_by(name=r).first()
            if not role:
                role = Role(name=r)
                db.add(role)
                db.commit()
                db.refresh(role)

        # Ensure first superuser
        admin = db.query(User).filter_by(email=settings.FIRST_SUPERUSER_EMAIL).first()
        if not admin:
            admin_role = db.query(Role).filter_by(name="admin").first()
            admin = User(
                email=settings.FIRST_SUPERUSER_EMAIL,
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
                is_active=True,
            )
            if admin_role:
                admin.roles.append(admin_role)
            db.add(admin)
            db.commit()
    finally:
        db.close()
