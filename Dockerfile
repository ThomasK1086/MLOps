# Use Python 3.11.4 as the base image
FROM python:3.11.4-slim

# Set working directory in the container
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN apt-get update && \
    apt-get install -y curl iputils-ping net-tools
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project directory into the container
COPY . .

# Run main_ex2.py when the container starts
CMD ["python", "main.py"]