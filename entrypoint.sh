#!/bin/sh
# entrypoint.sh

# This script acts as the container's entrypoint.
# The 'exec' command replaces the shell process with the command that follows.
# The 'nice -n -10' command runs the given command with a higher scheduling priority.
# A lower "niceness" value (-20 to 19) means a higher priority. -10 is a safe and effective value.
# "$@" passes all arguments from the Docker CMD to this script.
# In our case, it will pass "python", "src/main.py".

echo "Starting TatuBeats with higher CPU priority..."
exec nice -n -10 "$@"