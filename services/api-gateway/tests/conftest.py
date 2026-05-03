import sys
import os
from pathlib import Path

# Add repo root and service root to sys.path
# This file is at: [REPO_ROOT]/services/api-gateway/tests/conftest.py (Local)
# Or: /app/tests/conftest.py (Docker)

current_file = Path(__file__).resolve()

# 1. Add Service Root (the directory containing 'app')
# Locally: parents[1] is services/api-gateway
# Docker: parents[1] is /app
service_root = current_file.parents[1]
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

# 2. Add Repo Root (to find 'schemas')
# Locally: parents[3] is the repo root
# Docker: /app is the repo root (since we copy schemas into /app/schemas)
try:
    repo_root = current_file.parents[3]
except IndexError:
    # We are likely in a container where /app is the root
    repo_root = service_root

if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Ensure 'app' and 'schemas' are discoverable
os.environ["PYTHONPATH"] = f"{service_root}{os.pathsep}{repo_root}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"
