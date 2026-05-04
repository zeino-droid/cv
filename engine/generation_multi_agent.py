import json
import logging
from typing import Dict, Any, List
from google import genai
from google.genai import types
from engine.schemas import LLMCVData

logger = logging.getLogger(__name__)

class MultiAgentGenerator:
    """
    Pipeline de génération Multi-Agents (Axe 2).
    1. L'Agent 'Matcher' (idéalement BM25/Vector Search) sélectionne les expériences.
    2. L'Agent 'Writer' (Gemini) utilise `response_schema` pour forcer un output Pydantic strict.
    """
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def select_best_experiences(self, master_profile: Dict, job_description: str, max_items: int = 3) -> List[Dict]:
        """
        Agent 1: (Mockup/Heuristique pour l'instant)
        Sélectionne les meilleures expériences du profil sans LLM pour garantir la stabilité et réduire la latence.
        En production, remplacer par une recherche BM25 ou Cosine Similarity.
        """
        # Pour l'implémentation immédiate, on prend les premières priorisées du profil
        exps = master_profile.get("experience_stark", []) or master_profile.get("experiences", [])
        return exps[:max_items]

    def generate_cv_structure(self, selected_exps: List[Dict], job_offer: Dict) -> LLMCVData:
        """
        Agent 2: Le Writer.
        Utilise le SDK Google GenAI pour forcer un Structured Output strict (LLMCVData).
        """
        job_title = job_offer.get("title", "")
        job_desc = job_offer.get("description", "")
        
        # Contexte strict envoyé au LLM
        prompt = f"""
        Rédige le contenu d'un CV ciblé pour l'offre suivante :
        Poste : {job_title}
        Description : {job_desc}

        Utilise UNIQUEMENT les expériences fournies ci-dessous. 
        Pour chaque expérience, crée un maximum de 3 puces impactantes (focus métriques).

        EXPÉRIENCES SOURCE :
        {json.dumps(selected_exps, ensure_ascii=False, indent=2)}
        """

        try:
            logger.info("Envoi de la requête à Gemini avec Structured Outputs...")
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=LLMCVData,
                ),
            )
            
            # Le SDK retourne directement l'objet parsé si response_schema est défini
            return response.parsed
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération structurée : {e}", exc_info=True)
            raise e
