#!/bin/bash
# Run the orchestra-poc SDK spike. Assumes venv has already been created
# and deps installed via `pip install -r requirements.txt`.
set -euo pipefail
cd "$(dirname "$0")"
exec ./.venv/bin/python spike.py
