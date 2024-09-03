#!/bin/bash

# Define the path to the Python script
PYTHON_SCRIPT="./src/main.py"

# Check if the Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Main script not found!"
    exit 1
fi

python3.12 "$PYTHON_SCRIPT" "$@"
EXIT_CODE=$?

exit $EXIT_CODE
