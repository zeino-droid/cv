#!/usr/bin/env python3
"""
👻 GHOST-SOURCING (V1.0) — Autonomous Background Hunting
Moves from "User-Pull" to "System-Push".

Runs sourcing in the background, identifies "Golden" matches,
and automatically prepares CVs and Letters in the /vault.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from engine.sourcing.orchestrator import scan_jobs, list_target_profiles
from engine.cv_generator import PersonalCVGenerator
from engine.database import JobDatabase
from Pipeline import process_single_job

# Configuration
GOLDEN_THRESHOLD = 85  # Minimum score to trigger automatic generation
MAX_GOLDEN_PER_RUN = 5  # Safety cap to avoid burning LLM tokens
LOG_FILE = ROOT / "storage" / "ghost_sourcing.log"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("GhostSourcing")

async def run_ghost_sourcing():
    logger.info("👻 Starting Ghost-Sourcing session...")
    
    # 1. Initialize Engines
    db = JobDatabase()
    try:
        generator = PersonalCVGenerator()
    except Exception as e:
        logger.error(f"❌ Failed to initialize CV Generator: {e}")
        return

    # 2. Identify Profiles to Scan
    profiles = list_target_profiles()
    if not profiles:
        logger.warning("⚠️ No profiles found in master_profile.json. Aborting.")
        return
    
    # We'll scan for each profile to maximize coverage
    all_golden_jobs = []
    
    for profile in profiles:
        profile_key = profile["key"]
        logger.info(f"📡 Scanning for profile: {profile_key}...")
        
        try:
            results = scan_jobs(
                target_profile=profile_key,
                use_llm_expansion=True,
                use_llm_rerank=True,
                use_llm_skills=True,
                progress_callback=lambda p, m: logger.debug(f"[{profile_key}] {int(p*100)}% - {m}")
            )
            
            jobs = results.get("jobs", [])
            logger.info(f"✅ Found {len(jobs)} jobs for {profile_key}.")
            
            # Filter for Golden matches
            golden = [j for j in jobs if j.get("fit_score", 0) >= GOLDEN_THRESHOLD]
            
            for j in golden:
                j["profile_key"] = profile_key # Track which profile matched
                # Deduplicate within this run
                if not any(gj["id"] == j["id"] for gj in all_golden_jobs):
                    all_golden_jobs.append(j)
                    
        except Exception as e:
            logger.error(f"❌ Error scanning for {profile_key}: {e}")

    if not all_golden_jobs:
        logger.info("📭 No 'Golden' matches found today. See you tomorrow!")
        return

    # Sort by score
    all_golden_jobs.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
    logger.info(f"🌟 Found {len(all_golden_jobs)} total Golden matches!")

    # 3. Process Golden Jobs
    newly_generated = 0
    for job in all_golden_jobs[:MAX_GOLDEN_PER_RUN]:
        job_id = job.get("id")
        
        # Check if already generated or processed
        existing = db.get_job_by_id(job_id)
        if existing and existing.get("status") in ["generated", "sent", "applied"]:
            logger.info(f"⏩ Skipping {job.get('company')} - {job.get('title')} (Already processed)")
            continue
            
        logger.info(f"🔥 Auto-generating assets for: {job.get('company')} | {job.get('title')} (Score: {job.get('fit_score')})")
        
        try:
            # First, save/upsert to DB so process_single_job has a target
            db.upsert_jobs([job])
            
            # Generate CV & Letter
            # process_single_job is async
            row = await process_single_job(
                generator=generator,
                profile=generator.master_profile,
                job=job,
                use_llm_letter=True
            )
            
            # Update DB with paths and status
            db.save_generation(job_id, row["cv_path"], row["letter_path"])
            db.update_status(job_id, "generated", notes=f"👻 Ghost-Sourced on {datetime.now().strftime('%Y-%m-%d')}")
            
            newly_generated += 1
            logger.info(f"✅ Assets ready in /vault for {job.get('company')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to process {job.get('company')}: {e}")

    # 4. Final Notification
    if newly_generated > 0:
        msg = f"🔔 Ghost-Sourcing Alert: Found {newly_generated} 'Golden' matches today. CVs and Letters are already generated in your /vault. Review and click 'Send'?"
        logger.info(msg)
        # Create a notification file for the user to see
        notification_path = ROOT / "vault" / "LATEST_NOTIFICATION.md"
        with open(notification_path, "w", encoding="utf-8") as f:
            f.write(f"# 👻 Ghost-Sourcing Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write(f"{msg}\n\n")
            f.write("### 🚀 New Opportunities Ready:\n")
            for job in all_golden_jobs[:newly_generated]:
                f.write(f"- **{job.get('company')}** : {job.get('title')} (Score: {job.get('fit_score')})\n")
    else:
        logger.info("📉 No new Golden matches to process.")

if __name__ == "__main__":
    asyncio.run(run_ghost_sourcing())
