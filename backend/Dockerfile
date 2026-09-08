FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home greta
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
RUN mkdir -p /data/repository /data/files /data/queue && chown -R greta:greta /data /app
USER greta
ENV DATA_DIR=/data REPOSITORY_ROOT=/data/repository
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
