#!/bin/bash

# Define the path to the Python script
PYTHON_SCRIPT="./src/main.py"

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Main script not found!"
    exit 1
fi

# Loop to restart the Python script if it exits with code 2
while true; do
    python3.12 "$PYTHON_SCRIPT" "$@"
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 12 ]; then
        break
    fi
    echo "Restarting..."
done

exit $EXIT_CODE
