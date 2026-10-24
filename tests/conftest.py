# pytest runs this file before it imports any test module. The file does two jobs:
#   1. It puts the repo root on sys.path, so `import ffai` works with a bare `pytest`.
#   2. It points the database at a temporary file, so no test touches a real ffai.db.
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["FFAI_DB_PATH"] = os.path.join(tempfile.mkdtemp(prefix="ffai-test-"), "ffai.db")
