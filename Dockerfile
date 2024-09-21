FROM python:3.9.20-alpine3.20
WORKDIR /app
COPY app/ .
RUN apk update && apk add --no-cache \
    gcc \
    musl-dev \
    postgresql-dev \
    libpq \
    python3-dev && \
    pip install --no-cache-dir -r requirements.txt

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN chown -R appuser:appgroup /app
USER appuser
CMD ["python","app.py"]