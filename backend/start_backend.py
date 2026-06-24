"""Start backend server."""
import os
import subprocess
import sys
from pathlib import Path

# Change to the backend directory (relative to this script)
os.chdir(Path(__file__).parent)
subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])
