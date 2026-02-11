FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry==1.7.1

# Copy dependency files
COPY services/discord-service/pyproject.toml services/discord-service/poetry.lock* ./
COPY libs /libs/

# Install dependencies (no dev dependencies in production)
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-dev

# Copy source code
COPY services/discord-service/src/ ./src/
COPY services/discord-service/config/ ./config/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port for health checks
EXPOSE 8003

# Run the service
CMD ["python", "-m", "src.main"]
