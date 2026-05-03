# ─── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.12-alpine AS base

# Security: create a non-root user and group
RUN addgroup -g 1001 appgroup && \
    adduser -u 1001 -G appgroup -s /bin/sh -D appuser

# Working directory
WORKDIR /app

# Copy application source
COPY main.py .

# Fix permissions
RUN chown -R appuser:appgroup /app

# ─── Runtime stage ────────────────────────────────────────────────────────────
FROM base AS runtime

# Drop to non-root user
USER appuser

# Environment defaults (overridden by docker-compose)
ENV MODE=stable \
    APP_VERSION=1.0.0 \
    APP_PORT=3000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 3000

# Health check baked into image
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:${APP_PORT}/healthz')" || exit 1

CMD ["python3", "main.py"]