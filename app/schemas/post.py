from pydantic import BaseModel

class PostBase(BaseModel):
    title: str
    content: str

class PostCreate(PostBase):
    pass

class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None

class PostOut(PostBase):
    id: int
    author_id: int

    class Config:
        from_attributes = True
