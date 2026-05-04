import sys
import time
import signal
import logging
from typing import Dict, Any

# Assuming schedule is installed, if not fallback to simple sleep loop
try:
    import schedule
except ImportError:
    schedule = None

from engine.database import JobDatabase
from engine.sourcing.orchestrator import scan_jobs

# Configuration du logging de production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("SourcingWorker")

class SourcingDaemon:
    def __init__(self):
        self.running = True
        self.db = JobDatabase()
        
        # Gestion propre des signaux (Docker / Systemd)
        signal.signal(signal.SIGINT, self.handle_exit)
        signal.signal(signal.SIGTERM, self.handle_exit)

    def handle_exit(self, signum, frame):
        """Capte les signaux d'arrêt pour fermer proprement le worker."""
        logger.info(f"Signal {signum} reçu. Arrêt gracieux du worker en cours...")
        self.running = False

    def run_sourcing_job(self):
        """Tâche principale : scanne, filtre, et enregistre en base."""
        logger.info("Début du cycle de sourcing en arrière-plan...")
        try:
            # On lance le sourcing asynchrone via notre orchestrateur
            # On peut passer des paramètres spécifiques depuis la config
            results = scan_jobs(
                enable_france_travail=True,
                enable_adzuna=True,
                enable_companies_watcher=True,
                use_llm_expansion=False, # Évite d'exploser le quota LLM en arrière-plan
                use_llm_rerank=False,
                use_llm_skills=False
            )
            
            jobs_to_save = results.get("jobs", [])
            if not jobs_to_save:
                logger.info("Aucune nouvelle offre qualifiée trouvée lors de ce cycle.")
                return

            # Sauvegarde en base de données
            # L'orchestrateur a déjà écarté les offres existantes (optimisation précédente)
            self.db.upsert_jobs(jobs_to_save)
            logger.info(f"Cycle terminé. {len(jobs_to_save)} nouvelles offres sauvegardées.")
            
        except Exception as e:
            logger.error(f"Erreur critique lors du cycle de sourcing : {e}", exc_info=True)

    def start(self, interval_hours: int = 6):
        """Lance le daemon."""
        logger.info(f"Démarrage du Sourcing Daemon. Intervalle : {interval_hours} heures.")
        
        # Exécution immédiate au démarrage
        self.run_sourcing_job()
        
        if schedule:
            schedule.every(interval_hours).hours.do(self.run_sourcing_job)
            while self.running:
                schedule.run_pending()
                time.sleep(60)
        else:
            logger.warning("Package 'schedule' non installé. Utilisation d'une boucle sleep basique.")
            sleep_seconds = interval_hours * 3600
            while self.running:
                # Sleep fragmenté pour réagir rapidement au SIGTERM
                for _ in range(sleep_seconds):
                    if not self.running:
                        break
                    time.sleep(1)
                if self.running:
                    self.run_sourcing_job()
                    
        logger.info("Worker arrêté proprement.")

if __name__ == "__main__":
    worker = SourcingDaemon()
    worker.start(interval_hours=6)
