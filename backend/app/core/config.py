from pathlib import Path
import os
import json

BASE_DIR = Path(__file__).resolve().parents[3]
DATABASE_DIR = BASE_DIR / "database"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + str(DATABASE_DIR / "app.db"))
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def _env_bool(name: str, default: bool) -> bool:
	value = os.getenv(name)
	if value is None:
		return default
	return value.strip().lower() in {"1", "true", "yes", "on"}


SCHEDULER_ENABLED = _env_bool("SCHEDULER_ENABLED", False)
SCHEDULER_HOUR = int(os.getenv("SCHEDULER_HOUR", "5"))
SCHEDULER_MINUTE = int(os.getenv("SCHEDULER_MINUTE", "0"))
SCHEDULER_TIMEZONE = os.getenv("SCHEDULER_TIMEZONE", "America/New_York")


def _discovery_candidates() -> list[dict[str, str]]:
	try:
		value = json.loads(os.getenv("DISCOVERY_CANDIDATES", "[]"))
	except json.JSONDecodeError:
		return []
	return value if isinstance(value, list) and all(isinstance(item, dict) for item in value) else []


DISCOVERY_CANDIDATES = _discovery_candidates()
AUTOMATIC_DISCOVERY_ENABLED = _env_bool("AUTOMATIC_DISCOVERY_ENABLED", False)
DISCOVERY_CATALOG_URL = os.getenv("DISCOVERY_CATALOG_URL", "")
DISCOVERY_CATALOG_PROVIDER = os.getenv("DISCOVERY_CATALOG_PROVIDER", "public_json_catalog")
DISCOVERY_CATALOG_ALLOWED_HOSTS = tuple(
	host.strip() for host in os.getenv("DISCOVERY_CATALOG_ALLOWED_HOSTS", "").split(",") if host.strip()
)
ATS_CATALOG_DISCOVERY_ENABLED = _env_bool("ATS_CATALOG_DISCOVERY_ENABLED", False)
ATS_CATALOG_MANIFEST_URL = os.getenv(
	"ATS_CATALOG_MANIFEST_URL",
	"https://storage.stapply.ai/jobhive/v1/manifest.json",
)
AUTOMATIC_INGESTION_ENABLED = _env_bool("AUTOMATIC_INGESTION_ENABLED", False)
AUTOMATIC_INGESTION_MAX_SOURCES_PER_RUN = int(os.getenv("AUTOMATIC_INGESTION_MAX_SOURCES_PER_RUN", "10"))
AUTOMATIC_INGESTION_MAX_JOBS_PER_SOURCE = int(os.getenv("AUTOMATIC_INGESTION_MAX_JOBS_PER_SOURCE", "100"))
AUTOMATIC_INGESTION_TIMEOUT_SECONDS = int(os.getenv("AUTOMATIC_INGESTION_TIMEOUT_SECONDS", "30"))
