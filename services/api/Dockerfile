FROM python:3.12-slim

ARG INSTALL_DEV=true

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY migrations ./migrations

RUN if [ "$INSTALL_DEV" = "true" ]; then \
        pip install --no-cache-dir -e ".[dev]"; \
    else \
        pip install --no-cache-dir .; \
    fi \
    && chown -R app:app /app

USER 10001:10001

EXPOSE 8000

CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
