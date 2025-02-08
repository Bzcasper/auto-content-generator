# File: config.py
import os
from pathlib import Path

class Config:
    # API Configuration
    SUPABASE_URL = "https://vaubsaaeexjdgzpzuqcm.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZhdWJzYWFlZXhqZGd6cHp1cWNtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzgzOTUwMTQsImV4cCI6MjA1Mzk3MTAxNH0.SBOAxBIGbaVRxmYo_ms5pfAKXpfBw2K8snPaa5T0ms8"
    GROQ_API_KEY = "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"

    # Project paths
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)

    # Crawler settings
    MAX_CONCURRENT_REQUESTS = 3
    REQUEST_TIMEOUT = 30