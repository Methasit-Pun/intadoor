#!/bin/bash
# sync-up.sh - Upload local changes to the Raspberry Pi
REMOTE="raspberry@100.121.162.57"
DEST_DIR="~/Desktop/intadoor"

rsync -avz --progress \
  --exclude '__pycache__' \
  --exclude 'venv' \
  --exclude '.env' \
  "$(dirname "$0")/" \
  "$REMOTE:$DEST_DIR"
