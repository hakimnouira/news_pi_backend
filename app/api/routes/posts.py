from typing import List, Optional
import time
from pathlib import Path

from fastapi import (
    APIRouter, Depends, HTTPException, status,
    UploadFile, File, Form, Request
)
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db_dep, get_current_user
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostOut

router = APIRouter()

# ---- Upload config ----
UPLOAD_DIR = Path("static/uploads")
IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
VIDEO_EXT = {"mp4", "webm", "ogg", "mov", "mkv"}

def _ensure_owner(obj_author_id: int, user_id: int):
    if obj_author_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not owner")

def _detect_media_type(file: UploadFile) -> str:
    ct = (file.content_type or "").lower()
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ct.startswith("image/") or ext in IMAGE_EXT:
        return "image"
    if ct.startswith("video/") or ext in VIDEO_EXT:
        return "video"
    raise HTTPException(
        status_code=400,
        detail="Unsupported media format. Images: png/jpg/jpeg/gif/webp; Videos: mp4/webm/ogg/mov/mkv"
    )

def _save_upload(file: UploadFile) -> str:
    """Save file and return a *relative* /static path (e.g. '/static/uploads/123_name.png')."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{int(time.time())}_{Path(file.filename).name}"
    (UPLOAD_DIR / safe_name).write_bytes(file.file.read())
    return f"/static/uploads/{safe_name}"

def _abs(request: Request, rel_path: Optional[str]) -> Optional[str]:
    """Convert '/static/…' to absolute 'http://host:port/static/…'."""
    if not rel_path:
        return None
    base = str(request.base_url).rstrip("/")
    if rel_path.startswith("/"):
        return f"{base}{rel_path}"
    return f"{base}/{rel_path}"

@router.get("/", response_model=List[PostOut])
def list_posts(db: Session = Depends(get_db_dep)):
    return (
        db.query(Post)
        .options(joinedload(Post.author))        # eager-load author for username
        .order_by(Post.id.desc())
        .all()
    )

@router.post("/", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    request: Request,
    title: str = Form(...),
    content: str = Form(...),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    media_url_rel: Optional[str] = None
    media_type: Optional[str] = None

    if file:
        media_type = _detect_media_type(file)
        media_url_rel = _save_upload(file)

    post = Post(
        title=title,
        content=content,
        author_id=current_user.id,
        media_url=_abs(request, media_url_rel),   # store absolute URL
        media_type=media_type,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post

@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db_dep)):
    post = (
        db.query(Post)
        .options(joinedload(Post.author))         # eager-load author
        .get(post_id)
    )
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post

@router.put("/{post_id}", response_model=PostOut)
def update_post(
    request: Request,
    post_id: int,
    title: Optional[str] = Form(None),
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    clear_media: bool = Form(False),
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    _ensure_owner(post.author_id, current_user.id)

    if title is not None:
        post.title = title
    if content is not None:
        post.content = content

    if clear_media:
        post.media_url = None
        post.media_type = None

    if file:
        media_type = _detect_media_type(file)
        media_url_rel = _save_upload(file)
        post.media_type = media_type
        post.media_url = _abs(request, media_url_rel)

    db.add(post)
    db.commit()
    db.refresh(post)
    return post

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    _ensure_owner(post.author_id, current_user.id)

    db.delete(post)
    db.commit()
    return
