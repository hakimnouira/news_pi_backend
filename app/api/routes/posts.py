from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep, get_current_user
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostUpdate, PostOut

router = APIRouter()

def _ensure_owner(obj_author_id: int, user_id: int):
    if obj_author_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not owner")

@router.get("/", response_model=List[PostOut])
def list_posts(db: Session = Depends(get_db_dep)):
    return db.query(Post).order_by(Post.id.desc()).all()

@router.post("/", response_model=PostOut, status_code=status.HTTP_201_CREATED)
def create_post(
    post_in: PostCreate,
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    post = Post(title=post_in.title, content=post_in.content, author_id=current_user.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    return post

@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db_dep)):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post

@router.put("/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    post_in: PostUpdate,
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    _ensure_owner(post.author_id, current_user.id)

    if post_in.title is not None:
        post.title = post_in.title
    if post_in.content is not None:
        post.content = post_in.content

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
