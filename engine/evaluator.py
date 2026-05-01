import re
import json
from typing import Dict, Any

class AutoEval:
    """
    LLM-as-a-Judge or Heuristic Evaluator.
    Software 2.0 requires robust Evaluation metrics. 
    This class scores the generated CV against the Job Description.
    """
    
    @staticmethod
    def evaluate_cv_fit(cv_data: Dict[str, Any], job_offer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Computes a deterministic recall score: what percentage of the Job Description's
        required skills/keywords actually made it into the final CV text?
        """
        job_desc = job_offer.get("description", "").lower()
        if not job_desc:
            return {"score": 0.0, "missing_keywords": []}
            
        # Very basic keyword extraction from job (in a real system, use an LLM or TF-IDF to extract n-grams)
        required_keywords = [
            kw for kw in job_offer.get("required_skills", []) 
            if isinstance(kw, str) and len(kw) > 2
        ]
        
        # If the pipeline didn't extract required_skills natively, we fall back to a naive split
        if not required_keywords:
            required_keywords = [
                w.strip() for w in re.split(r'\W+', job_desc) 
                if len(w.strip()) > 5 # proxy for 'technical terms'
            ][:20]
            
        cv_text = json.dumps(cv_data).lower()
        
        hits = 0
        misses = []
        for kw in required_keywords:
            kw_lower = kw.lower()
            if kw_lower in cv_text:
                hits += 1
            else:
                misses.append(kw)
                
        total = len(required_keywords)
        score = (hits / total) * 100 if total > 0 else 0.0
        
        return {
            "score": round(score, 1),
            "keyword_recall": f"{hits}/{total}",
            "missing_keywords": misses[:5] # Top 5 missing
        }
