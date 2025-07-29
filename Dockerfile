# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r voiceai && useradd -r -g voiceai voiceai

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    portaudio19-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY pyproject.toml ./
COPY README.md ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -e .

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create necessary directories
RUN mkdir -p /app/logs /app/data && \
    chown -R voiceai:voiceai /app

# Switch to non-root user
USER voiceai

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.append('.'); from src.health import check_health; check_health()" || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "-m", "src.main"]