import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Keep automated tests completely separate from the real application database.
TEST_DATABASE_PATH = Path(os.getenv("TEST_DATABASE_PATH", f"/tmp/contract_ai_test_{os.getpid()}.db"))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH}"
