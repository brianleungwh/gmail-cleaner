# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

# Copy frontend package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Build frontend with Docker flag (outputs to ./dist)
ENV DOCKER_BUILD=true
RUN npm run build && \
    echo "=== Build complete, checking output ===" && \
    ls -la ./dist/

# Stage 2: Python application
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml ./
COPY uv.lock ./

# Install Python dependencies
RUN uv pip install --system -e .

# Copy application code
COPY app/ ./app/
COPY gmail_cleaner.py ./

# Copy built frontend from frontend-builder stage
# The build outputs to ./dist in Docker builds
COPY --from=frontend-builder /frontend/dist ./app/static

# Verify static files were copied
RUN echo "=== Verifying static files ===" && \
    ls -la ./app/static/ && \
    ls -la ./app/static/assets/ || echo "No assets directory found"

# Create data directory for credentials
RUN mkdir -p /app/data

# Set default log level (can be overridden in docker-compose or at runtime)
ENV LOG_LEVEL=INFO

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]