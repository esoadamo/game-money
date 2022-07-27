#!/bin/bash
echo "Entry"
cd "$(realpath "$(dirname "$0")")/.." || { echo "ERR: Cannot cd to script dir"; exit 1; }

source venv/bin/activate
python app.py

