FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including those needed for skia-python
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    git \
    libgl1 \
    libegl1 \
    libgles2 \
    libfontconfig1 \
    libfreetype6 \
    libicu-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Create cache directory for images
RUN mkdir -p /app/cache

# Expose port 5001
EXPOSE 5001

# Run the proxy on 0.0.0.0 to allow LAN access
CMD ["python", "proxy.py", "--host", "0.0.0.0", "--port", "5001"]