"""
📊 Logic for Job Application Analytics and Conversion Funnels.
"""

import pandas as pd
from typing import Dict, List
from engine.database import JobDatabase

class AnalyticsEngine:
    def __init__(self, db: JobDatabase):
        self.db = db

    def get_funnel_stats(self) -> Dict:
        """Calculates global funnel statistics."""
        stats = self.db.get_stats()
        
        # Sent vs Interviews
        sent = stats.get("sent", 0)
        interviews = stats.get("interviews", 0)
        offers = stats.get("offers", 0)
        
        response_rate = (interviews / sent * 100) if sent > 0 else 0
        offer_rate = (offers / interviews * 100) if interviews > 0 else 0
        
        return {
            "sent": sent,
            "interviews": interviews,
            "offers": offers,
            "response_rate": round(response_rate, 1),
            "offer_rate": round(offer_rate, 1),
        }

    def get_headline_performance(self) -> pd.DataFrame:
        """Analyzes performance by CV headline."""
        jobs = self.db.get_jobs(limit=1000)
        if not jobs:
            return pd.DataFrame()
            
        df = pd.DataFrame(jobs)
        if "final_headline" not in df.columns or df["final_headline"].empty:
            return pd.DataFrame()

        # Clean headlines (take only the prefix before " : ")
        df["headline_clean"] = df["final_headline"].fillna("N/A").apply(lambda x: x.split(" : ")[0] if " : " in str(x) else x)
        
        # Performance by headline
        perf = df.groupby("headline_clean").agg(
            total=("id", "count"),
            sent=("status", lambda x: sum(x.isin(["sent", "applied", "interview", "offer", "rejected"]))),
            interviews=("status", lambda x: sum(x == "interview")),
            offers=("status", lambda x: sum(x == "offer"))
        ).reset_index()
        
        perf["response_rate"] = (perf["interviews"] / perf["sent"] * 100).fillna(0).round(1)
        perf = perf[perf["sent"] > 0].sort_values("response_rate", ascending=False)
        
        return perf

    def get_model_performance(self) -> pd.DataFrame:
        """Analyzes performance by LLM model used."""
        jobs = self.db.get_jobs(limit=1000)
        if not jobs:
            return pd.DataFrame()
            
        df = pd.DataFrame(jobs)
        if "generation_model" not in df.columns:
            df["generation_model"] = "Unknown"
        
        df["generation_model"] = df["generation_model"].fillna("Unknown")
        
        # Performance by model
        perf = df.groupby("generation_model").agg(
            total=("id", "count"),
            sent=("status", lambda x: sum(x.isin(["sent", "applied", "interview", "offer", "rejected"]))),
            interviews=("status", lambda x: sum(x == "interview")),
            offers=("status", lambda x: sum(x == "offer"))
        ).reset_index()
        
        perf["response_rate"] = (perf["interviews"] / perf["sent"] * 100).fillna(0).round(1)
        perf = perf[perf["sent"] > 0].sort_values("response_rate", ascending=False)
        
        return perf

    def export_to_csv(self, path: str = "tracker.csv"):
        """Exports the entire database to a CSV file for manual tracking."""
        jobs = self.db.get_jobs(limit=5000)
        df = pd.DataFrame(jobs)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path
