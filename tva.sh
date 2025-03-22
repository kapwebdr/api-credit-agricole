#!/bin/sh
source .venv/bin/activate
pip install -r requirements.txt
python process_ca_pdf.py