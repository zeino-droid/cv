"""
Dashboard Job Copilot — La Tour de Contrôle
Architecture modulaire Phase 3.
"""

import streamlit as st
from engine.database import JobDatabase, STATUS_EMOJI
from ui.pages.job_detail import render_job_detail

# Configuration de la page
st.set_page_config(
    page_title="Job Copilot — Tour de Contrôle",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

db = JobDatabase()

def init_session_state():
    """Initialise toutes les variables critiques au démarrage."""
    defaults = {
        "current_page": "Liste À Traiter",
        "selected_job_id": None,
        "generation_status": "idle",
        "generated_cv_data": None,
        "edited_headline": None,
        "edited_summary": None,
        "pack_ready": False,
        "application_sent": False,
        "location_filter": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def render_sidebar():
    """Rendu de la barre latérale pour la navigation."""
    with st.sidebar:
        st.title("🚀 Job Copilot")
        st.caption("Objectif CDI France 2026")
        st.divider()
        
        # Navigation principale
        pages = ["Liste À Traiter", "Tracker", "🔍 Scanner", "👤 Profil"]
        st.session_state["current_page"] = st.radio("Navigation", pages)
        
        st.divider()
        # Statistiques rapides
        stats = db.get_stats()
        st.metric("Candidatures Envoyées", stats["sent"])
        st.metric("Entretiens", stats["interviews"])
        
        if st.button("🔄 Actualiser les données"):
            st.rerun()

def render_todo_list():
    """Affiche la liste des offres à traiter (new/selected)."""
    st.header("📋 Liste À Traiter")
    st.write("Sélectionne une offre pour générer ton CV et postuler.")
    
    # Récupération des jobs (new et selected)
    new_jobs = db.get_jobs_by_status("new")
    selected_jobs = db.get_jobs_by_status("selected")
    all_todo = selected_jobs + new_jobs
    
    if not all_todo:
        st.info("Aucune offre à traiter. Va dans le Scanner pour en trouver !")
        return

    # Tableau simplifié
    for job in all_todo:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                emoji = STATUS_EMOJI.get(job["status"], "•")
                st.markdown(f"**{emoji} {job['title']}**")
                st.caption(f"{job.get('company')} — {job.get('location')}")
            with col2:
                st.write(f"Fit: **{job['fit_score']}%**")
            with col3:
                if st.button("Traiter", key=f"btn_{job['id']}", use_container_width=True):
                    st.session_state["selected_job_id"] = job["id"]
                    st.session_state["current_page"] = "Détail Offre"
                    st.session_state["generation_status"] = "idle" # Reset status for new selection
                    st.rerun()

def main():
    init_session_state()
    render_sidebar()
    
    page = st.session_state["current_page"]
    
    if page == "Liste À Traiter":
        render_todo_list()
        
    elif page == "Détail Offre":
        if st.session_state["selected_job_id"]:
            if st.button("⬅️ Retour à la liste"):
                st.session_state["current_page"] = "Liste À Traiter"
                st.session_state["selected_job_id"] = None
                st.rerun()
            render_job_detail(st.session_state["selected_job_id"])
        else:
            st.session_state["current_page"] = "Liste À Traiter"
            st.rerun()
            
    elif page == "Tracker":
        st.header("📊 Tracker de Candidatures")
        st.info("Cette section sera enrichie en Phase 4.")
        # On peut garder un aperçu simple
        sent_jobs = db.get_jobs_by_status("sent")
        if sent_jobs:
            st.dataframe(sent_jobs)
        else:
            st.write("Aucune candidature envoyée pour le moment.")
            
    elif page == "🔍 Scanner":
        st.header("🔍 Scanner de Marché")
        st.warning("Module de scan en cours de migration vers l'architecture Phase 3.")
        
    elif page == "👤 Profil":
        st.header("👤 Mon Profil Master")
        st.info("Visualisation du profil maître.")

if __name__ == "__main__":
    main()
