from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.db.database import init_db
import warnings
warnings.filterwarnings("ignore", message=".*error reading bcrypt version.*")

app = FastAPI(
    title="News PI Backend",
    version="0.1.0",
    openapi_url="/openapi.json",
)

# CORS (adjust for your frontends)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    # Create tables and seed base data if needed
    init_db()


@app.get("/", tags=["health"])
def read_root():
    return {"status": "ok", "app": app.title, "version": app.version}


# Mount all API routes
app.include_router(api_router, prefix=settings.API_V1_STR)
