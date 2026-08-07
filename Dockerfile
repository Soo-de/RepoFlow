# ==========================================
# Stage 1: Builder
# Builds virtual environment and installs dependencies
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Prevent Python from writing bytecode (.pyc) and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a virtual environment to isolate installed dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip to ensure smooth package installation
RUN pip install --no-cache-dir --upgrade pip

# Copy dependency specification and source code
COPY pyproject.toml README.md ./
COPY app ./app/

# Install project dependencies into the virtual environment
RUN pip install --no-cache-dir .

# ==========================================
# Stage 2: Runner
# Final minimal container image for execution
# ==========================================
FROM python:3.12-slim AS runner

WORKDIR /app

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Install system dependencies (git and SSL certificates required for cloning repositories)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user for security best practices
RUN addgroup --system appgroup && adduser --system --group appuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code into destination directory
COPY app ./app/

# Assign ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose container port
EXPOSE 8000

# Launch Uvicorn server hosting the FastAPI application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
