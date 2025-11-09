import os
from dotenv import load_dotenv

# Charger le fichier .env
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import api_router
from app.core.config import settings
from app.db.database import init_db
import warnings
from app.api.routes.summarizer import init_summarizer_services, shutdown_summarizer_services

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
    """Initialisation au démarrage"""
    # Create tables and seed base data if needed
    init_db()
    
    #Initialiser les services du summarizer
    init_summarizer_services()


@app.on_event("shutdown")
async def on_shutdown():
    """Nettoyage à l'arrêt"""
    #Arrêter proprement les services du summarizer
    shutdown_summarizer_services()


@app.get("/", tags=["health"])
def read_root():
    return {"status": "ok", "app": app.title, "version": app.version}


# Mount all API routes
app.include_router(api_router, prefix=settings.API_V1_STR)