"""
engine/link_rescue.py
Recherche de lien de secours pour les offres expirées.
Utilise une recherche Google automatisée.
"""

import urllib.parse
import requests
from typing import Optional


def build_google_search_url(job_offer: dict) -> str:
    """Construit une URL de recherche Google pour retrouver l'offre."""
    titre = job_offer.get("titre", job_offer.get("title", ""))
    entreprise = job_offer.get("entreprise", job_offer.get("company", ""))
    query = f'"{titre}" "{entreprise}" offre emploi site:linkedin.com OR site:indeed.fr OR site:welcometothejungle.com'
    return f"https://www.google.com/search?q={urllib.parse.quote(query)}"


def check_url_alive(url: str, timeout: int = 5) -> bool:
    """Vérifie si une URL répond (non expirée)."""
    if not url:
        return False
    try:
        resp = requests.head(url, timeout=timeout, allow_redirects=True)
        return resp.status_code < 400
    except Exception:
        return False


def search_fallback_links(job_offer: dict) -> list[dict]:
    """
    Tente de trouver des liens alternatifs via l'API SerpApi si configurée,
    sinon retourne juste l'URL de recherche Google manuelle.
    """
    import os

    titre = job_offer.get("titre", job_offer.get("title", ""))
    entreprise = job_offer.get("entreprise", job_offer.get("company", ""))

    results = []

    # Option 1 : SerpApi (si clé disponible)
    serpapi_key = os.environ.get("SERPAPI_KEY", "")
    if serpapi_key:
        try:
            query = f"{titre} {entreprise} offre emploi"
            resp = requests.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": serpapi_key,
                    "num": 5,
                    "hl": "fr",
                    "gl": "fr",
                },
                timeout=10,
            )
            data = resp.json()
            for r in data.get("organic_results", [])[:5]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("link", ""),
                    "snippet": r.get("snippet", ""),
                    "source": "SerpApi",
                })
        except Exception:
            pass

    # Option 2 : Fallback manuel — lien Google direct
    google_url = build_google_search_url(job_offer)
    results.append({
        "title": f"Recherche Google : {titre} @ {entreprise}",
        "url": google_url,
        "snippet": "Cliquez pour rechercher manuellement sur Google",
        "source": "Google Search",
    })

    # Option 3 : Liens directs vers les principales job boards
    for board, base in [
        ("LinkedIn", f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(titre + ' ' + entreprise)}"),
        ("Indeed", f"https://fr.indeed.com/jobs?q={urllib.parse.quote(titre)}&l={urllib.parse.quote(entreprise)}"),
        ("WTTJ", f"https://www.welcometothejungle.com/fr/jobs?query={urllib.parse.quote(titre)}"),
    ]:
        results.append({
            "title": f"Chercher sur {board}",
            "url": base,
            "snippet": f"Recherche directe sur {board}",
            "source": board,
        })

    return results
