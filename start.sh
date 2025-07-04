#!/bin/sh

# This script is run when the VM starts.

# Exit immediately if a command exits with a non-zero status.
set -e

# The path where the database should be inside the volume.
DB_PATH="/data/stats.db"

# The public URL to your pre-populated database file.
# IMPORTANT: Replace this with the link you copied from Discord!
DOWNLOAD_URL="https://cdn.discordapp.com/attachments/1385355185903108221/1390679987983618099/stats.db?ex=6869232a&is=6867d1aa&hm=109a9031c47cf56ab9228a3da10b781706f49faabe07776e84044e1e2eb9211c&"

# Check if the database file does NOT exist in the volume.
if [ ! -f "$DB_PATH" ]; then
  echo "Database not found at $DB_PATH. Downloading initial version..."
  # Use wget to download the file from the URL and save it to the correct path.
  # The -O flag specifies the output file path.
  wget -O "$DB_PATH" "$DOWNLOAD_URL"
  echo "Download complete."
else
  echo "Database already exists at $DB_PATH. Skipping download."
fi

# Now, start the actual application.
# The 'exec' command replaces the shell process with the Python process,
# which is the proper way to end a start-up script.
echo "Starting MestreTatu Bot..."
exec python src/main.py