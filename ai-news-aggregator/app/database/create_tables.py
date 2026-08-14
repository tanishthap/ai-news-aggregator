"""One-off script: create every table defined in models.py.

Run with:
    uv run python -m app.database.create_tables
"""

from __future__ import annotations

from .models import Base
from .session import engine


def create_tables() -> None:
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    create_tables()
    print("Tables created.")
