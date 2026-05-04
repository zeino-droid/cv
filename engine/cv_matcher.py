import logging
from typing import List, Dict

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)

class LocalExperienceMatcher:
    """
    Agent 1 : Scorage et sélection d'expériences par approche TF-IDF.
    Extrêmement rapide, n'utilise pas l'API LLM pour économiser de la latence et des tokens.
    Sans dépendances lourdes comme Torch ou Transformers.
    """
    def __init__(self, language: str = 'french'):
        self.language = language
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn n'est pas installé. Le matcher utilisera un fallback chronologique.")

    def _build_experience_document(self, exp: Dict) -> str:
        """Construit un document textuel riche pour l'expérience (STAR-K + Description)."""
        components = [
            exp.get("title", ""),
            exp.get("company", ""),
            exp.get("description", ""),
            exp.get("S", ""),  # Situation
            exp.get("T", ""),  # Task
            exp.get("A", ""),  # Action
            exp.get("R", ""),  # Result
        ]
        # Ajouter les mots clés (K) s'ils existent
        keywords = exp.get("K", [])
        if isinstance(keywords, list):
            components.extend(keywords)
        elif isinstance(keywords, str):
            components.append(keywords)
            
        return " ".join([str(c) for c in components if c])

    def select_top_experiences(self, master_experiences: List[Dict], job_description: str, top_k: int = 3) -> List[Dict]:
        """
        Sélectionne les top_k expériences les plus sémantiquement proches de l'offre.
        """
        if not master_experiences:
            return []
            
        if not SKLEARN_AVAILABLE or not job_description.strip():
            # Fallback trivial si sklearn est absent ou description vide
            return master_experiences[:top_k]
            
        # 1. Préparation du corpus (les documents d'expérience)
        documents = [self._build_experience_document(exp) for exp in master_experiences]
        
        # 2. Vectorisation TF-IDF
        # On inclut la description du job à la fin pour la vectoriser dans le même espace
        corpus = documents + [job_description]
        
        # On peut ignorer les stopwords anglais par défaut. Pour le FR, on laisse par défaut.
        vectorizer = TfidfVectorizer() 
        tfidf_matrix = vectorizer.fit_transform(corpus)
        
        # 3. Calcul de similarité cosinus
        # La description du poste est le dernier vecteur de la matrice
        job_vector = tfidf_matrix[-1]
        exp_vectors = tfidf_matrix[:-1]
        
        # .flatten() pour obtenir un array 1D des scores
        similarities = cosine_similarity(job_vector, exp_vectors).flatten()
        
        # 4. Tri et sélection (argsort donne l'ordre croissant, on inverse)
        top_indices = similarities.argsort()[-top_k:][::-1]
        
        top_experiences = [master_experiences[i] for i in top_indices]
        
        logger.info(f"Top {len(top_experiences)} expériences sélectionnées via TF-IDF Cosine Similarity.")
        for rank, idx in enumerate(top_indices):
            title = master_experiences[idx].get('title', 'Expérience Sans Titre')
            logger.info(f" Match #{rank+1} : {title} (Score de pertinence : {similarities[idx]:.3f})")
            
        return top_experiences

    def score_experiences_dict(self, master_experiences: List[Dict], job_description: str) -> Dict[str, float]:
        """
        Retourne un dictionnaire {exp_id: score_tfidf} pour toutes les expériences.
        """
        if not master_experiences:
            return {}
            
        if not SKLEARN_AVAILABLE or not job_description.strip():
            return {exp.get("id", f"exp_{i}"): 0.0 for i, exp in enumerate(master_experiences)}
            
        documents = [self._build_experience_document(exp) for exp in master_experiences]
        corpus = documents + [job_description]
        
        try:
            vectorizer = TfidfVectorizer() 
            tfidf_matrix = vectorizer.fit_transform(corpus)
            job_vector = tfidf_matrix[-1]
            exp_vectors = tfidf_matrix[:-1]
            similarities = cosine_similarity(job_vector, exp_vectors).flatten()
            
            scores = {}
            for i, exp in enumerate(master_experiences):
                exp_id = exp.get("id", f"exp_{i}")
                scores[exp_id] = float(similarities[i])
            return scores
        except Exception as e:
            logger.warning(f"Erreur TF-IDF: {e}")
            return {exp.get("id", f"exp_{i}"): 0.0 for i, exp in enumerate(master_experiences)}

