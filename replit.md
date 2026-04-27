# Job Copilot — Studio de Candidature

App Streamlit personnelle pour **Zein ELAJAMY** (ENSEM 2026, R&D Simulation Engineer chez ArcelorMittal) afin de trouver et candidater à des postes CDI en France dans la simulation numérique (CFD/FEM/Abaqus/Ansys/Python).

## Stack

- **Streamlit** (port 5000) — UI single-page : Smart Match → Studio modale → Archives
- **SQLite** (`storage/jobs.db`) — pipeline d'offres + candidatures
- **Google Gemini** (`google-genai`) — scoring sémantique, expansion mots-clés, extraction skills, génération de CV/LM
- **Typst** — rendu PDF des CV et lettres de motivation

## Architecture du sourcing — France-First (multi-source officiel)

L'ancien moteur basé sur scraping (JobSpy via Google Jobs / Glassdoor) a été retiré : trop instable, anti-pattern. Le nouveau pipeline mise sur **3 sources stables** appelées en parallèle (`ThreadPoolExecutor`) :

```
engine/sourcing/
├── __init__.py            → expose scan_jobs()
├── orchestrator.py        → pipeline complet (3 sources en parallèle + dédup + score + IA)
├── ranking.py             → Gemini helpers + scoring heuristique + dédup + rerank + extract skills
├── france_travail.py      → API officielle FR (OAuth2, ROME, départements)
├── adzuna.py              → agrégateur européen (cache 24h, 1000 req/mois free)
├── companies_watcher.py   → watcher actif sur Greenhouse/Lever/Workable/SmartRecruiters
├── _cache.py              → cache disque générique 24h
└── _utils.py              → helpers (stable_id)
```

### Les 3 sources

1. **🇫🇷 France Travail** (CORE) — API officielle de l'État, gratuit & illimité.
   Filtre par codes ROME (H1206 R&D industriel, H1402 méthodes, H1502 qualité, H2502 production, H1208 automatisme, H1404 industrialisation) + département.
   Auth OAuth2 client_credentials. Inscription gratuite : https://francetravail.io/

2. **🌍 Adzuna** — agrégateur européen, complément utile.
   Free tier : 1000 req/mois → cache disque 24h.

3. **🎯 Companies Watcher** — l'innovation : surveille activement les pages carrières d'employeurs français curés (`profiles/target_companies.yaml`) via leurs APIs ATS publiques :
   - Greenhouse Job Board API (Datadog, Stripe, Mirakl, Algolia…)
   - Lever Postings API (BlaBlaCar, Doctolib…)
   - Workable Widget API
   - SmartRecruiters Public Postings API (Dassault Systèmes, ArcelorMittal, Safran, Thales, TotalEnergies, Schneider, Forvia, Valeo…)

### Pipeline de scoring partagé

1. Expansion sémantique des mots-clés (Gemini, cache 7j)
2. Fan-out parallèle vers les 3 sources
3. Déduplication multi-niveaux (URL exacte → hash strict → Jaccard ≥ 0.75 par entreprise)
4. Scoring heuristique (alias compétences FEM/EF/FEA, premium keywords, freshness, location bonus)
5. Re-rank IA top-25 (Gemini)
6. Extraction de compétences clés top-15 (Gemini)
7. Filtre `min_score` (avec fallback top-25 si trop strict)

### Configuration

- `profiles/search_config.yaml` — codes ROME, mots-clés, départements, scoring
- `profiles/target_companies.yaml` — liste curatée des employeurs cibles + catégories UI
- `.env` — `GEMINI_API_KEY`, `FT_CLIENT_ID`/`FT_CLIENT_SECRET`, `ADZUNA_APP_ID`/`ADZUNA_APP_KEY`

Aucune clé n'est obligatoire : si une clé manque, la source correspondante est désactivée gracieusement avec un message clair dans l'UI ("ajoute FT_CLIENT_ID dans Secrets, inscription gratuite 5 min sur francetravail.io").

## UI — Recherche automatique (Dashboard.py, tab_auto)

UI minimale, un seul bouton **"🚀 Trouver mes offres"** :

- Bandeau de statut des 3 sources (vert si clés OK, jaune avec lien d'inscription sinon)
- Multi-select **Départements** (75/92/78/69/31/33/38/06/13/44…)
- Multi-select **Catégories d'employeurs** (éditeurs simu / aéro / énergie / auto / tech R&D…)
- Mots-clés additionnels optionnels
- 3 toggles IA (expansion / re-rank / extraction skills) — auto-désactivés si Gemini absent
- Pattern asynchrone existant conservé : `ThreadPoolExecutor + threading.Event` permet d'annuler la recherche en cours sans perdre les offres déjà collectées.

## Autres modules

- `engine/database.py` — SQLite, statuts, upsert idempotent, ID stable hash MD5
- `engine/cv_generator.py` — génération CV/LM via Gemini + rendu Typst
- `engine/prompts.py` — prompts factorisés
- `Sniper.py` — CLI standalone fast-apply (utilise `scan_jobs()` aussi)

## Tests

`tests/` : `test_database.py`, `test_cv_generator_unit.py`, `test_matching.py`, `test_prompts.py`, `integrity_check.py`. Le test JobSpy a été retiré avec l'ancien module.

## Important — Préférences utilisateur

- Tout en français (UI, prompts, configs).
- **Pas de scraping fragile** — uniquement des APIs officielles avec contrats stables.
- **France-First** — ne pas ramener du job board US (LinkedIn US, Indeed US…). Tout doit être pertinent pour un CDI en France.
- Préserver le pattern asynchrone d'annulation.
- Tout changement architectural majeur doit être documenté ici.
