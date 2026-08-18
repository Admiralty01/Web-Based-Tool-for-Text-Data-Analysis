import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, documents, analysis

# Setup logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create database tables at startup (SQLAlchemy automatic bootstrapping)
try:
    logger.info("Initializing PostgreSQL schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")
except Exception as e:
    logger.error(f"Failed to initialize database tables: {e}")

# Instantiate FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for front-end visualizers
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
if allowed_origins_env == "*":
    allowed_origins = ["*"]
    allow_credentials = False
else:
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include endpoint routers
app.include_router(
    auth.router, 
    prefix=f"{settings.API_V1_STR}/auth", 
    tags=["Authentication"]
)
app.include_router(
    documents.router, 
    prefix=settings.API_V1_STR, 
    tags=["Documents & Search"]
)
app.include_router(
    analysis.router, 
    prefix=settings.API_V1_STR, 
    tags=["NLP & Representation Analysis"]
)


# Mount static files (create app/static/ folder dynamically if not present)
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def read_root():
    """Serves the TextSynthetix Dashboard at the root path."""
    index_file = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_file):
        return HTMLResponse(
            content="<h1>TextSynthetix Dashboard API is running. index.html not found in static/ directory.</h1>",
            status_code=200
        )
    with open(index_file, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/health", tags=["Health Check"])
def health_check():
    """Verify application service status."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "api_prefix": settings.API_V1_STR,
        "docs_url": "/docs"
    }
