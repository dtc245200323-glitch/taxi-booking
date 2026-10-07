FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -m app
COPY requirements-qr.txt .
RUN pip install --no-cache-dir --timeout 20 --retries 2 --progress-bar off -r requirements-qr.txt
COPY app.py .
COPY media_payments.py .
COPY maps.py .
COPY promotions.py .
COPY migrate.py .
COPY db/auth.sql ./db/auth.sql
COPY static ./static
USER app
EXPOSE 8000
CMD ["sh", "-c", "python migrate.py && exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --access-logfile - app:app"]
