import logging
import asyncio
from typing import List, Dict, Optional

_logger = logging.getLogger(__name__)

class RippleEngine:
    """
    🗺️ Competitor 'Ripple' Search Engine
    Identifies competitors and their career pages based on a target company.
    """
    
    def __init__(self, llm=None):
        self.llm = llm
        if not self.llm:
            from engine.cv_generator import PersonalCVGenerator
            try:
                gen = PersonalCVGenerator()
                self.llm = gen.llm
            except Exception as e:
                _logger.error(f"Failed to initialize LLM for RippleEngine: {e}")

    async def identify_competitors(self, company: str, job_title: str) -> List[Dict[str, str]]:
        """
        Returns a list of top 5 competitors with their estimated career page URLs.
        """
        if not self.llm:
            return []

        prompt = f"""
        Tu es un expert en intelligence économique et en recrutement industriel.
        L'utilisateur s'intéresse au poste de "{job_title}" chez "{company}".
        
        Identifie les 5 principaux concurrents directs de "{company}" qui effectuent le même type de R&D ou d'ingénierie.
        Pour chaque concurrent, fournis :
        1. Le nom de l'entreprise
        2. Le secteur industriel précis
        3. L'URL directe probable de leur page carrières (Career Page).
        
        Réponds UNIQUEMENT avec un objet JSON au format suivant :
        [
          {{
            "name": "Nom de l'entreprise",
            "sector": "Secteur",
            "url": "https://company.com/careers"
          }},
          ...
        ]
        """
        
        try:
            response = await self.llm.generate(prompt, temperature=0.2)
            import json
            import re
            
            # Clean JSON if LLM added markdown
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return json.loads(response)
        except Exception as e:
            _logger.error(f"Ripple search failed for {company}: {e}")
            return []

    def get_google_career_link(self, company: str) -> str:
        """Fallback helper for career page search."""
        query = f"{company} careers jobs"
        return f"https://www.google.com/search?q={query.replace(' ', '+')}"

def get_ripple_search(company: str, job_title: str):
    """Sync wrapper if needed for Streamlit (though async is preferred via run_coroutine_sync)."""
    engine = RippleEngine()
    import asyncio
    # Note: In Dashboard.py, use run_coroutine_sync(engine.identify_competitors(...))
    return engine
