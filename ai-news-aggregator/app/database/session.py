"""Database engine + session factory.

Reads DATABASE_URL from the environment (see .env.example, loaded via
python-dotenv). Defaults match docker-compose.yml's defaults so a fresh
checkout works with zero config once the container is up.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/ai_news_aggregator",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, class_=Session)
