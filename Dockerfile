# Step 1: Official lightweight Python runtime
FROM python:3.12-slim

# Step 2: Environment settings (prevent bytecode generation & ensure unbuffered logging)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/attendance.db

# Step 3: Set working directory
WORKDIR /app

# Step 4: Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Copy application source code
COPY app/ ./app/

# Step 6: Create persistent data directory and non-root user for security
RUN mkdir -p /app/data && \
    useradd -u 1000 -m appuser && \
    chown -R appuser:appuser /app

USER appuser

# Step 7: Expose port 5000 for Flask and Prometheus metrics
EXPOSE 5000

# Step 8: Container health check using built-in Python urllib
HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/healthz')" || exit 1

# Step 9: Launch application
CMD ["python", "-m", "app.app"]
