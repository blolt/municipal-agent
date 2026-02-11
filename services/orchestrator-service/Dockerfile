FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.7.1

# Set working directory
WORKDIR /app

# Copy dependency files
COPY services/orchestrator-service/pyproject.toml services/orchestrator-service/poetry.lock* ./
COPY libs /libs

# Install dependencies
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY services/orchestrator-service .

# Install the package
RUN poetry install --no-interaction --no-ansi

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run the application
CMD ["uvicorn", "orchestrator_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
