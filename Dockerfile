FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install base Python packages from requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- BEST PRACTICE: Update yt-dlp during the build ---
# This ensures the image itself contains the latest version.
RUN python -m pip install -U yt-dlp

# Copy all necessary application code
COPY src/main.py .
COPY src/cogs/ ./cogs/

# The CMD is now simpler and only needs to run the bot.
CMD ["python", "main.py"]