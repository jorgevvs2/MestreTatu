# Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir makes the image smaller
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container at /app
# This will copy the entire 'src' directory, including 'rpg_books'
COPY src/ ./src/

# Command to run the application
CMD ["python", "src/main.py"]