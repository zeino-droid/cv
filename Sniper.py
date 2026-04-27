import asyncio
import argparse
import webbrowser
from pathlib import Path
from datetime import datetime
from engine.database import JobDatabase
from engine.cv_generator import PersonalCVGenerator
from engine.sourcing import scan_jobs

async def fast_apply_flow(top_n=10, min_score=60, scan=False):
    db = JobDatabase("storage/jobs.db")
    generator = PersonalCVGenerator()
    
    if scan:
        print("\n📡 Scanning for new jobs (France-First multi-source)...")
        result = scan_jobs(progress_callback=lambda p, m: print(f"   [{int(p*100):3d}%] {m}"))
        new_jobs = result.get("jobs", []) if isinstance(result, dict) else []
        db.upsert_jobs(new_jobs)
        print(f"✅ Found and scored {len(new_jobs)} jobs.")
        for w in (result.get("warnings", []) if isinstance(result, dict) else []):
            print(f"   ⚠️  {w}")

    # Fetch top jobs to apply
    jobs = db.get_jobs(status="new", min_score=min_score, limit=top_n)
    
    if not jobs:
        print(f"ℹ️ No new jobs with score >= {min_score}%. Try --min-score 40 or --scan.")
        return

    print(f"\n🚀 Starting Fast Apply for {len(jobs)} jobs...")
    
    for i, job in enumerate(jobs):
        print(f"\n[{i+1}/{len(jobs)}] {job['title']} @ {job['company']} ({job['fit_score']}%)")
        print(f"🔗 URL: {job['url']}")
        
        # 1. Generate adapted CV
        try:
            render_result = await generator.generate_cv_for_job(job)
            pdf_path = render_result.get("pdf_path")
            
            if pdf_path and Path(pdf_path).exists():
                print(f"✅ CV generated: {pdf_path}")
            else:
                print("⚠️ CV generation failed or PDF not created.")
        except Exception as e:
            print(f"❌ Error generating CV: {e}")
            continue

        # 2. Open URL and output folder
        print("🌍 Opening application URL...")
        webbrowser.open(job["url"])
        
        # 3. User choice
        choice = input("\n👉 Press ENTER when applied, 's' to skip, 'q' to quit: ").lower().strip()
        
        if choice == 'q':
            break
        elif choice == 's':
            print("⏭️ Skipped.")
            continue
        else:
            db.update_status(job["id"], "sent")
            print("✅ Status updated to 'sent'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fast Apply CLI — Converge to your CDI")
    parser.add_argument("--top", type=int, default=10, help="Number of jobs to process")
    parser.add_argument("--min-score", type=int, default=60, help="Minimum fit score")
    parser.add_argument("--scan", action="store_true", help="Run a fresh scan before applying")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(fast_apply_flow(top_n=args.top, min_score=args.min_score, scan=args.scan))
    except KeyboardInterrupt:
        print("\n👋 Stopped.")
