from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# Handle postgres scheme deprecated in SQLAlchemy 1.4+
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Handle SQLite threading check
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create engine with pool pre-ping to ensure active connection check
engine = create_engine(
    db_url, 
    pool_pre_ping=True,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency generator to retrieve database session for API requests."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
