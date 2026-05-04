from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sys
from pathlib import Path
import json
from datetime import datetime

# Add project root to sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from engine.database import JobDatabase

app = FastAPI(title="Job Copilot Clipper API")

# Enable CORS for browser extensions and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = JobDatabase(str(ROOT / "storage" / "jobs.db"))

class JobClip(BaseModel):
    title: str
    company: str | None = "Unknown"
    location: str | None = "Unknown"
    description: str | None = ""
    url: str | None = ""
    source: str | None = "Clipper"

@app.post("/clip")
async def clip_job(clip: JobClip):
    try:
        # Prepare job for database
        job_data = {
            "id": f"CLIP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{abs(hash(clip.title + (clip.company or '')))}",
            "title": clip.title,
            "company": clip.company or "Unknown",
            "location": clip.location or "Unknown",
            "description": clip.description or "",
            "url": clip.url or "",
            "source": clip.source or "Clipper",
            "fit_score": 0,  # Will be scored later by the engine
            "matched_skills": [],
            "required_skills": [],
            "status": "new",
            "sourcing_date": datetime.now().strftime("%Y-%m-%d"),
        }
        
        # Upsert into database
        new_count = db.upsert_jobs([job_data])
        
        return {
            "status": "success",
            "message": "Job clipped successfully",
            "job_id": job_data["id"],
            "is_new": new_count > 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
