#!/bin/sh
source .venv/bin/activate
pip install -r requirements.txt
uvicorn ca_api:app --host 0.0.0.0 --port 8000 --reload --reload-include "*.py"