from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + str(BASE_DIR / "database" / "app.db"))
