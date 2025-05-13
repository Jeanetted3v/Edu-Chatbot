FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.in requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ /app/config/
COPY src/backend/ /app/src/backend/
COPY src/__init__.py /app/src/__init__.py

# Create a non-root user
RUN adduser --disabled-password --gecos "" appuser
# Switch to production image
FROM builder AS runtime

# Set environment variables
# Set environment variables with default empty value if not already defined
ENV PYTHONPATH="/app"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Switch to non-root user
USER appuser

CMD ["python", "-m", "src.backend.api.main"]