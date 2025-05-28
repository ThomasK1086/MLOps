FROM python:3.11.4-slim

WORKDIR /app

# Copy only requirements.txt to install dependencies
COPY requirements.txt .

# Install system dependencies
RUN apt-get update && \
    apt-get install -y curl iputils-ping net-tools git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install uv
RUN uv pip install --no-cache-dir -r requirements.txt --system

CMD ["python", "main.py"]