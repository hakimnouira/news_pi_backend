from sqlalchemy import Column, Integer, String, Boolean, Table, ForeignKey, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.database import Base

user_role = Table(
    "user_role",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)  # NEW
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)                 # NEW
    last_name: Mapped[str | None]  = mapped_column(String(100), nullable=True)                 # NEW
    bio: Mapped[str | None]        = mapped_column(Text, nullable=True)                        # NEW
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)                      # NEW

    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    roles = relationship("Role", secondary=user_role, back_populates="users")
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")
