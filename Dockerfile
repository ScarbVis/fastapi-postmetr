# Use Python 3.13-slim as the base image
FROM python:3.11-slim

# Install system dependencies for building Python packages (e.g., numpy)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc && \
    rm -rf /var/lib/apt/lists/*

# Set a working directory
WORKDIR /app

# Copy requirements first so Docker can cache them (if they don't change)
COPY requirements.txt /app/

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app/

# Expose port 3000 (or whichever port you want to use)
EXPOSE 3000

# Run FastAPI via Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
