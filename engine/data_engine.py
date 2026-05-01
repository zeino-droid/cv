import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

class DataEngine:
    """
    Software 2.0 Data Flywheel.
    Every time you manually correct the LLM's output in the UI, this class captures the delta
    (Prompt + Original Output -> Your Corrected Output) and logs it as a training example.
    This creates a perfect Supervised Fine-Tuning (SFT) dataset to train a custom model later.
    """
    def __init__(self, dataset_dir: str = "storage/dataset"):
        self.dataset_dir = Path(dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.dataset_dir / "sft_training_data.jsonl"

    def log_user_correction(self, job: Dict[str, Any], raw_llm_data: Dict[str, Any], final_user_data: Dict[str, Any]):
        """
        Logs the manual overrides as a high-quality human label.
        """
        # Only log if there's an actual difference (user made an edit)
        if raw_llm_data == final_user_data:
            return

        example = {
            "timestamp": datetime.now().isoformat(),
            "job_id": job.get("id", "unknown"),
            "job_title": job.get("title", ""),
            "job_description": job.get("description", ""),
            "model_input": "Generate a CV for this job...", # In a real scenario, we'd log the exact prompt
            "rejected_output": raw_llm_data, # The raw LLM generation that you didn't like
            "chosen_output": final_user_data, # Your manually edited, perfect version (The Ground Truth)
        }

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(example, ensure_ascii=False) + "\n")

# Global singleton
data_engine = DataEngine()
