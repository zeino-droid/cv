"""
Client API France Travail v2 (ex Pôle Emploi) — la source de référence FR.

Doc officielle : https://francetravail.io/data/api/offres-emploi
Inscription gratuite (5 min) sur https://francetravail.io/

Auth : OAuth2 client_credentials, scope "api_offresdemploiv2 o2dsoffre"
Endpoint search : https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search

Filtres principaux utilisés :
  - codeROME      : 1 à plusieurs codes ROME (ex H1206 R&D industriel)
  - typeContrat   : "CDI" | "CDD" | …
  - departement   : codes département (ex 75,69,31)
  - publieeDepuis : 1 / 3 / 7 / 14 / 31 jours
  - range         : pagination "0-49" (max 150 par requête)

Si FT_CLIENT_ID / FT_CLIENT_SECRET absents : retourne [] + WARN, sans planter.
"""

from __future__ import annotations

import os
import random
import time
from datetime import date
from threading import Lock
from typing import Callable, Dict, List, Optional, Tuple

import requests

from engine.sourcing._cache import get_cache, set_cache
from engine.sourcing._utils import stable_id  # noqa: F401

AUTH_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"
TIMEOUT = 25

# Cache token (expiration 24 h côté France Travail, on prend une marge)
_token_lock = Lock()
_token_cache: Dict[str, object] = {"value": None, "expires_at": 0.0}


def has_credentials() -> bool:
    return bool(os.getenv("FT_CLIENT_ID") and os.getenv("FT_CLIENT_SECRET"))


def _get_token() -> Optional[str]:
    """OAuth2 client_credentials — token mis en cache jusqu'à expiration."""
    if not has_credentials():
        return None

    with _token_lock:
        if _token_cache["value"] and time.time() < float(_token_cache["expires_at"]):
            return str(_token_cache["value"])

        try:
            resp = requests.post(
                AUTH_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": os.environ["FT_CLIENT_ID"],
                    "client_secret": os.environ["FT_CLIENT_SECRET"],
                    "scope": SCOPE,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                print(f"   ⚠️  France Travail auth failed ({resp.status_code}): {resp.text[:200]}")
                return None
            data = resp.json()
            token = data.get("access_token")
            ttl = int(data.get("expires_in", 1500))
            _token_cache["value"] = token
            _token_cache["expires_at"] = time.time() + max(60, ttl - 60)
            return token
        except Exception as exc:
            print(f"   ⚠️  France Travail auth error: {exc}")
            return None


def _normalize(item: Dict) -> Optional[Dict]:
    """Convertit une offre FT brute → format job standard du projet."""
    title = (item.get("intitule") or "").strip()
    if not title:
        return None
    company = ""
    entreprise = item.get("entreprise") or {}
    if isinstance(entreprise, dict):
        company = (entreprise.get("nom") or "").strip()
    if not company:
        company = (item.get("nomEntreprise") or "Entreprise non communiquée").strip()

    lieu = item.get("lieuTravail") or {}
    if isinstance(lieu, dict):
        ville = (lieu.get("libelle") or "").strip()
    else:
        ville = ""
    location = ville or "France"

    description = (item.get("description") or "").strip()
    url = (item.get("origineOffre", {}) or {}).get("urlOrigine") or ""
    if not url:
        # URL canonique France Travail
        url = f"https://candidat.francetravail.fr/offres/recherche/detail/{item.get('id', '')}"

    posted = (item.get("dateCreation") or "")[:10]
    contrat = (item.get("typeContrat") or "").upper() or "CDI"

    job_id = stable_id("FT", item.get("id", ""), title, company)
    return {
        "id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "description": description,
        "url": url,
        "source": "france_travail",
        "required_skills": [],
        "matched_skills": [],
        "extracted_skills": [],
        "job_type": contrat,
        "sourcing_date": date.today().isoformat(),
        "posted_date": posted,
    }


def _invalidate_token() -> None:
    """Invalide le token en cache (à utiliser sur 401)."""
    with _token_lock:
        _token_cache["value"] = None
        _token_cache["expires_at"] = 0.0


def _search_one(
    rome_codes: Optional[List[str]] = None,
    mots_cles: Optional[str] = None,
    departement: Optional[str] = None,
    type_contrat: str = "CDI",
    publiee_depuis: int = 31,
    range_str: str = "0-49",
    max_retries: int = 3,
) -> Tuple[List[Dict], str]:
    """
    Effectue une requête /offres/search avec gestion robuste des erreurs.

    Supporte 2 modes de recherche (combinables) :
      - `rome_codes` : codes ROME métier (ex H1206)
      - `mots_cles`  : recherche textuelle libre (ex "ingénieur simulation CFD")

    Retourne `(jobs, status)` où `status` ∈ {
        "ok"            : réponse OK (peut contenir 0 résultat = fin de pagination),
        "auth_failed"   : token invalide après retry → arrêter la session,
        "rate_limited"  : 429 persistant après backoff → arrêter la pagination,
        "http_error"    : autre erreur HTTP → arrêter la pagination,
        "network_error" : exception réseau → arrêter la pagination.
    }

    Différence clé : un 0 résultat ("ok" + liste vide) signale la fin de pagination,
    alors qu'un 429 ne doit PAS être interprété comme une fin de pages.
    """
    params: Dict[str, object] = {
        "typeContrat": type_contrat,
        "publieeDepuis": publiee_depuis,
        "range": range_str,
    }
    if rome_codes:
        params["codeROME"] = ",".join(rome_codes)
    if mots_cles:
        params["motsCles"] = mots_cles
    if departement:
        params["departement"] = departement
    # Au moins un critère de recherche
    if not rome_codes and not mots_cles:
        return [], "ok"

    cache_key = repr(sorted(params.items()))
    cached = get_cache("france_travail", cache_key, ttl_seconds=86400)
    if cached is not None:
        return cached, "ok"

    for attempt in range(max_retries + 1):
        token = _get_token()
        if not token:
            return [], "auth_failed"

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        try:
            resp = requests.get(
                SEARCH_URL, headers=headers, params=params, timeout=TIMEOUT
            )
        except Exception as exc:
            print(f"   ⚠️  France Travail request failed: {exc}")
            return [], "network_error"

        if resp.status_code in (200, 206):
            data = resp.json() or {}
            items = data.get("resultats", []) or []
            normalized = [n for n in (_normalize(i) for i in items) if n]
            set_cache("france_travail", cache_key, normalized)
            return normalized, "ok"

        if resp.status_code == 204:
            # Pas de contenu = aucun résultat sur ce range
            set_cache("france_travail", cache_key, [])
            return [], "ok"

        if resp.status_code == 401:
            # Token rejeté : on invalide le cache et on retente avec un token frais.
            print(f"   ⚠️  France Travail 401 (tentative {attempt + 1}/{max_retries + 1}) — refresh token.")
            _invalidate_token()
            if attempt >= max_retries:
                return [], "auth_failed"
            time.sleep(0.5)
            continue

        if resp.status_code == 429:
            # Rate-limit : backoff exponentiel + jitter, puis retry.
            if attempt >= max_retries:
                print("   ⚠️  France Travail 429 persistant — abandon de cette tranche.")
                return [], "rate_limited"
            wait = (2 ** attempt) + random.uniform(0.0, 0.7)
            retry_after = resp.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = max(wait, float(retry_after))
            print(f"   ⏳ France Travail 429 — backoff {wait:.1f}s (tentative {attempt + 1}/{max_retries + 1}).")
            time.sleep(wait)
            continue

        # Autre erreur HTTP → on stoppe proprement la pagination
        print(f"   ⚠️  France Travail search failed ({resp.status_code}): {resp.text[:200]}")
        return [], "http_error"

    return [], "http_error"


def search(
    rome_codes: Optional[List[str]] = None,
    keyword_queries: Optional[List[str]] = None,
    departments: Optional[List[str]] = None,
    type_contrat: str = "CDI",
    publiee_depuis: int = 31,
    max_per_query: int = 100,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> List[Dict]:
    """
    Recherche multi-départements avec 2 stratégies combinées :
      1. Par codes ROME (tous les ROME en une requête)
      2. Par mots-clés textuels (`motsCles`) — un appel par groupe de mots-clés

    Si `departments` est vide ou None : recherche nationale.
    Renvoie une liste de jobs au format standard, dédupliquée par id.
    """
    if not rome_codes and not keyword_queries:
        return []

    # Sanity-check des credentials avant de lancer (le _get_token() est appelé
    # à chaque tentative dans _search_one, ce qui gère naturellement le 401).
    if not has_credentials():
        print("   ⚠️  France Travail : credentials absents (FT_CLIENT_ID / FT_CLIENT_SECRET).")
        print("       Inscription gratuite : https://francetravail.io/")
        return []

    targets: List[Optional[str]] = list(departments) if departments else [None]
    out: Dict[str, Dict] = {}

    # --- Stratégie 1 : recherche par codes ROME ---
    if rome_codes:
        for dep in targets:
            if should_stop and should_stop():
                break

            if progress_callback:
                label = dep or "national"
                progress_callback(0.0, f"🇫🇷 France Travail · ROME · {label}")

            page_size = 49
            start = 0
            while start < max_per_query:
                if should_stop and should_stop():
                    break
                end = min(start + page_size, max_per_query - 1)
                range_str = f"{start}-{end}"
                results, status = _search_one(
                    rome_codes=rome_codes,
                    departement=dep,
                    type_contrat=type_contrat,
                    publiee_depuis=publiee_depuis,
                    range_str=range_str,
                )

                if status == "auth_failed":
                    return list(out.values())
                if status != "ok":
                    break
                if not results:
                    break

                for job in results:
                    out[job["id"]] = job

                if len(results) < page_size + 1:
                    break
                start = end + 1
                time.sleep(0.4)  # politesse

    # --- Stratégie 2 : recherche par mots-clés textuels ---
    if keyword_queries:
        for kw_query in keyword_queries:
            if should_stop and should_stop():
                break

            for dep in targets:
                if should_stop and should_stop():
                    break

                if progress_callback:
                    label = dep or "national"
                    progress_callback(0.0, f"🇫🇷 France Travail · \"{kw_query}\" · {label}")

                page_size = 49
                start = 0
                # Limiter la pagination par mots-clés à 50 résultats (pour ne pas cramer le quota)
                kw_max = min(max_per_query, 50)
                while start < kw_max:
                    if should_stop and should_stop():
                        break
                    end = min(start + page_size, kw_max - 1)
                    range_str = f"{start}-{end}"
                    results, status = _search_one(
                        mots_cles=kw_query,
                        departement=dep,
                        type_contrat=type_contrat,
                        publiee_depuis=publiee_depuis,
                        range_str=range_str,
                    )

                    if status == "auth_failed":
                        return list(out.values())
                    if status != "ok":
                        break
                    if not results:
                        break

                    for job in results:
                        out[job["id"]] = job

                    if len(results) < page_size + 1:
                        break
                    start = end + 1
                    time.sleep(0.4)  # politesse

    return list(out.values())
