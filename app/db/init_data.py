# app/db/init_data.py
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.database import SessionLocal
from app.models.user import User
from app.models.role import Role
from app.core.security import get_password_hash

def _unique_username(db: Session, base: str) -> str:
    # sanitize a bit
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
        # Ensure roles exist
        for r in ("admin", "user"):
            role = db.query(Role).filter_by(name=r).first()
            if not role:
                role = Role(name=r)
                db.add(role)
                db.commit()
                db.refresh(role)

        # Ensure first superuser (now with username)
        admin = db.query(User).filter_by(email=settings.FIRST_SUPERUSER_EMAIL).first()
        if not admin:
            admin_role = db.query(Role).filter_by(name="admin").first()

            # derive username from email local part and make it unique
            email_local = (settings.FIRST_SUPERUSER_EMAIL or "admin").split("@")[0]
            username = _unique_username(db, email_local)
            print("DEBUG → FIRST_SUPERUSER_PASSWORD:", repr(settings.FIRST_SUPERUSER_PASSWORD))
            print("DEBUG → Length:", len(get_password_hash(settings.FIRST_SUPERUSER_PASSWORD)))
            admin = User(
                email=settings.FIRST_SUPERUSER_EMAIL,
                username=username,                      # <<< IMPORTANT
                first_name="Admin",
                last_name="User",
                hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),  
                is_active=True,
            )
            
            if admin_role:
                admin.roles.append(admin_role)

            db.add(admin)
            db.commit()
    finally:
        db.close()
