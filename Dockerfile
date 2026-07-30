FROM python:3.10-slim

# Set environment variables
ENV DISPLAY=:99
ENV PYTHONUNBUFFERED=1

# Install system dependencies including Xvfb
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install PyTorch CPU-only first to optimize image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install python dependencies
COPY config/requirements.txt config/requirements.txt
RUN pip install --no-cache-dir -r config/requirements.txt

# Install Playwright browser and system dependencies
RUN playwright install chromium --with-deps

# Copy application files
COPY . .

# Ensure entrypoint script is executable
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "scripts/cron_naukri_apply.py"]
