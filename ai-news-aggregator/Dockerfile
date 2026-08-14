# Standard uv Docker pattern: install deps first (cached layer), then
# copy the rest of the code. https://docs.astral.sh/uv/guides/integration/docker/
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependencies only, so this layer is cached until pyproject.toml/uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Now the actual app code.
COPY . .
RUN uv sync --frozen

# Default: run one ingestion pass. Override the command to run something
# else, e.g.:
#   docker compose run app uv run python -m app.database.create_tables
CMD ["uv", "run", "python", "-m", "app.runner"]
