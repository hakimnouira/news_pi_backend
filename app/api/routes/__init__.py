from fastapi import APIRouter
from . import auth, users, posts, comments, roles , newscheck
api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(comments.router, prefix="/comments", tags=["comments"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(newscheck.router, prefix="/newscheck", tags=["newscheck"])
