#!/bin/bash

# Find the true root directory where this script is located
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# If the script was placed inside the scripts folder, go up one level
if [[ "$ROOT_DIR" == */scripts ]]; then
  ROOT_DIR="$(dirname "$ROOT_DIR")"
fi

# 1. Automatically detect the correct Python alias
if command -v python3 &>/dev/null; then
  PY_CMD="python3"
elif command -v python &>/dev/null; then
  PY_CMD="python"
else
  echo "Error: Python is not installed or not in your PATH."
  exit 1
fi

# 2. Check for a local virtual environment and use it if present
if [ -d "$ROOT_DIR/.venv" ]; then
  source "$ROOT_DIR/.venv/bin/activate"
elif [ -d "$ROOT_DIR/venv" ]; then
  source "$ROOT_DIR/venv/bin/activate"
fi

# 3. Check if python-dotenv is installed (optional but highly recommended)
if ! $PY_CMD -c "import dotenv" &>/dev/null; then
  echo "Tip: Install 'python-dotenv' to securely manage local API keys."
fi

# Help usage check
if [ "$#" -lt 2 ]; then
  echo "Usage: ./generate.sh <TYPE> <ID1> [ID2] [ID3] ..."
  echo "Example: ./generate.sh network 213 49"
  echo "Example (Reversed): ./generate.sh 213 network"
  exit 1
fi

# Detect if the user passed an ID first instead of the type
if [[ "$1" =~ ^[0-9]+$ ]]; then
  TYPE="${@: -1}"
  IDS=("${@:1:$#-1}")
else
  TYPE=$1
  shift
  IDS=("$@")
fi

# Updated validation
if [[ "$TYPE" != "network" && "$TYPE" != "company" && "$TYPE" != "genre" && "$TYPE" != "provider" ]]; then
    echo "Error: Type must be 'network', 'company', 'genre', or 'provider'. Received: '$TYPE'"
    exit 1
fi

# Loop through the IDs one by one
for ID in "${IDS[@]}"; do
  echo "=================================================="
  echo " Processing ID: $ID ($TYPE)"
  echo "=================================================="

  echo "── 1. Pulling & Processing Logos..."
  $PY_CMD "$ROOT_DIR/scripts/logo_pull.py" --id "$ID" --type "$TYPE" --max 2

  echo ""
  echo "── 2. Generating T1 Backdrops..."
  $PY_CMD "$ROOT_DIR/scripts/backdrop_T1.py" --id "$ID" --type "$TYPE"

  echo ""
  echo "── 3. Generating T2 Backdrops..."
  $PY_CMD "$ROOT_DIR/scripts/backdrop_T2.py" --id "$ID" --type "$TYPE"

  echo ""
  echo " ✓ Done with ID: $ID"
  echo "=================================================="
  echo ""
done

echo "★ All collections generated successfully! ★"