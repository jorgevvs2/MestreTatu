# Dockerfile

# --- Stage 1: Builder ---
# Use a more recent and secure base image. Bookworm is the current stable Debian.
FROM python:3.10-slim-bookworm AS builder

# Copy only the requirements file to leverage Docker's layer cache.
COPY requirements.txt .

# Install Python dependencies into the standard location for this Python version.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# --- Stage 2: Final Image ---
# This stage builds the final, lean image for your bot.
FROM python:3.10-slim-bookworm

# Set the working directory inside the container
WORKDIR /app

# --- THE FIX ---
# Copy the installed packages from the builder's site-packages directory
# to the same location in the final image.
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages

# Copy your bot's source code into the image
COPY src/ ./src/

# Ensure logs are not buffered
ENV PYTHONUNBUFFERED=1

# The command to run when the container starts.
# No need for PYTHONPATH, as we copied the packages to the standard location.
CMD ["python", "-m", "src.main"]