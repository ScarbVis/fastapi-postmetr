# Use Python 3.13 (development or nightly build) as the base image
# Note: This may not be officially supported yet. Replace this with a valid 3.13 image if needed.
FROM python:3.13-slim

# Set a working directory
WORKDIR /app

# Copy requirements first so Docker can cache them (if they don't change)
COPY requirements.txt /app/

# Install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . /app/

# Expose port 8000 (or whichever port you want to use)
EXPOSE 8000

# Run FastAPI via Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
