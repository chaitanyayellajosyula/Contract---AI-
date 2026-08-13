from fastapi import FastAPI

from app.api import auth_router, candidates_router, companies_router, dashboard_router, jobs_router, recruiters_router, vendor_contacts_router, vendors_router
from app.core.bootstrap import bootstrap_admin
from app.core.database import SessionLocal, initialize_database
from app.models import user, team

app = FastAPI(
    title="Contract Hunter AI API",
    description="Application foundation for Contract Hunter AI.",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(candidates_router)
app.include_router(companies_router)
app.include_router(dashboard_router)
app.include_router(jobs_router)
app.include_router(vendor_contacts_router)
app.include_router(vendors_router)
app.include_router(recruiters_router)

initialize_database()

with SessionLocal() as session:
    bootstrap_admin(session)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
