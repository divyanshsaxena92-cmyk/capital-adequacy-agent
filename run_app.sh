#!/usr/bin/env bash
# Start the front end:  ./run_app.sh   then open http://localhost:8501
cd "$(dirname "$0")"
python -m streamlit run app.py
