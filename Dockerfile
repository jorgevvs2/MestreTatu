# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# --- FIX: Install system dependencies for Plotly/Kaleido, including Chromium ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Full Chromium browser, which Kaleido needs to render images
    chromium \
    # Fonts required by Chromium
    fonts-liberation \
    # Existing dependencies for headless operation
    libnss3 \
    libgconf-2-4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libasound2 \
    # Clean up the apt cache to keep the image size down
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
COPY . .

# Make port 8080 available to the world outside this container
# This is for the health check endpoint for services like Cloud Run
EXPOSE 8080

# Define the command to run your app
CMD ["python", "src/main.py"]