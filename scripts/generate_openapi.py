#!/usr/bin/env python3
"""Generate OpenAPI JSON spec from the FastAPI app.

Usage:
    python scripts/generate_openapi.py > docs/openapi.json
"""

import json
import sys
import os

# Ensure the source is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set minimal env vars so config loading doesn't fail
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "idgenerator")
os.environ.setdefault("DB_USER", "postgres")
os.environ.setdefault("DB_PASSWORD", "postgres")

from id_generator.main import app  # noqa: E402

spec = app.openapi()
print(json.dumps(spec, indent=2))
