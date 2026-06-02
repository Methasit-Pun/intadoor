#!/bin/bash
# sync-down.sh - Download remote changes from the Raspberry Pi
REMOTE="raspberry@100.121.162.57"
SRC_DIR="~/Desktop/intadoor"

rsync -avz --progress \
  --exclude '__pycache__' \
  --exclude 'venv' \
  "$REMOTE:$SRC_DIR/" \
  "$(dirname "$0")/"
