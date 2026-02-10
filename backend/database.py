from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database is MariaDB/MySQL; use mysql+pymysql in connection string
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"local_infile": True},  # For LOAD DATA LOCAL INFILE (file upload into DB)
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
