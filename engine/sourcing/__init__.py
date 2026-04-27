"""
Job Copilot — Sourcing France-First.

3 sources stables remplaçant l'ancien moteur scraping (JobSpy) :
  • france_travail   — API officielle de l'État (OAuth2, gratuit, ROME)
  • adzuna           — agrégateur européen (1000 req/mois gratuites)
  • companies_watcher — APIs ATS publiques (Greenhouse / Lever / Workable)
                        des employeurs simu/R&D France curés

Point d'entrée unique : engine.sourcing.orchestrator.scan_jobs(...)
"""

from engine.sourcing.orchestrator import scan_jobs  # noqa: F401
