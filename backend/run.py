"""
Development application server launcher.
"""
import os
import sys
from pathlib import Path

# Add project root to python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app import create_app

app = create_app(os.getenv("FLASK_ENV", "development"))

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

    print(f"===============================================================")
    print(f"  AI Document Intelligence Server running on http://{host}:{port}")
    print(f"===============================================================")
    app.run(host=host, port=port, debug=debug)

