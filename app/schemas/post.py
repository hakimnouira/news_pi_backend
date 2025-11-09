from pydantic import BaseModel


class PostBase(BaseModel):
    title: str
    content: str


class PostCreate(PostBase):
    # In FastAPI we will receive media (image/video) via FormData,
    # so the file itself is not declared here (only fields)
    pass


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    # Optionally allow replacing/clearing the media
    media_url: str | None = None
    media_type: str | None = None


class PostOut(PostBase):
    id: int
    author_id: int

    # ✅ Added fields
    media_url: str | None = None   # path or url of the uploaded file
    media_type: str | None = None  # "image" or "video"

    class Config:
        from_attributes = True
