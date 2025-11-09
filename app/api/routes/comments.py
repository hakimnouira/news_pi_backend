from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db_dep, get_current_user
from app.models.comment import Comment
from app.models.post import Post
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentUpdate, CommentOut

router = APIRouter()

def _ensure_owner(obj_author_id: int, user_id: int):
    if obj_author_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not owner")

@router.get("/", response_model=List[CommentOut])
def list_comments(db: Session = Depends(get_db_dep)):
    return db.query(Comment).order_by(Comment.id.desc()).all()

@router.get("/post/{post_id}", response_model=List[CommentOut])
def list_comments_for_post(post_id: int, db: Session = Depends(get_db_dep)):
    return db.query(Comment).filter(Comment.post_id == post_id).order_by(Comment.id.desc()).all()

@router.post("/post/{post_id}", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def create_comment_for_post(
    post_id: int,
    comment_in: CommentCreate,
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    post = db.query(Post).get(post_id)
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    comment = Comment(content=comment_in.content, post_id=post_id, author_id=current_user.id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

@router.put("/{comment_id}", response_model=CommentOut)
def update_comment(
    comment_id: int,
    comment_in: CommentUpdate,
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    comment = db.query(Comment).get(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    _ensure_owner(comment.author_id, current_user.id)

    if comment_in.content is not None:
        comment.content = comment_in.content
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db_dep),
    current_user: User = Depends(get_current_user),
):
    comment = db.query(Comment).get(comment_id)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    _ensure_owner(comment.author_id, current_user.id)

    db.delete(comment)
    db.commit()
    return
