# Production Container for Vera Autonomous Retailer Agent
# magicpin AI Challenge Final Candidate

FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install pinned dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and canonical datasets
COPY vera ./vera
COPY dataset ./dataset
COPY bot.py .
COPY CHALLENGE_SPEC.md .

# Create non-privileged user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

# Health check against production liveness probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:8080/v1/healthz || exit 1

CMD ["uvicorn", "bot:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
