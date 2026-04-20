"""
Page de détail d'une offre d'emploi — Visualisation, Génération et Édition.
"""

import streamlit as st
import asyncio
from engine.database import JobDatabase
from engine.cv_generator import PersonalCVGenerator
from ui.components.action_block import render_action_block

db = JobDatabase()

def render_job_detail(job_id: str):
    """Rendu principal de la page de détail."""
    job = db.get_job_by_id(job_id)
    if not job:
        st.error("Offre introuvable.")
        return

    # 1. Visualisation
    render_visualization_section(job)
    
    st.divider()
    
    # 2. Trigger de génération
    render_generation_trigger(job)
    
    # 3. Édition et Actions (si généré)
    if st.session_state.get("generation_status") == "done" or job.get("cv_path"):
        render_edit_section(job)
        st.divider()
        render_action_block(job)

def render_visualization_section(job: dict):
    """Affiche les informations de base de l'offre."""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.title(job["title"])
        st.subheader(f"🏢 {job.get('company', 'Inconnu')} — 📍 {job.get('location', 'France')}")
    
    with col2:
        score = job.get("fit_score", 0)
        color = "green" if score >= 70 else "orange" if score >= 40 else "red"
        st.metric("Score de Fit", f"{score}%")
        st.markdown(f'<div style="height:10px; width:100%; background-color:{color}; border-radius:5px;"></div>', unsafe_allow_html=True)

    with st.expander("📖 Voir la description complète"):
        st.markdown(job.get("description", "Aucune description disponible."))

def render_generation_trigger(job: dict):
    """Gère le bouton de génération du CV."""
    if job.get("cv_path") and st.session_state.get("generation_status") != "generating":
        st.success(f"✅ CV déjà généré le {job.get('updated_at')}")
        if st.button("🔄 Régénérer le CV"):
            st.session_state["generation_status"] = "idle"
            st.rerun()
        return

    status = st.session_state.get("generation_status", "idle")
    
    if status == "idle":
        if st.button("🚀 Générer mon CV sur-mesure", type="primary", use_container_width=True):
            st.session_state["generation_status"] = "generating"
            st.rerun()
            
    elif status == "generating":
        with st.spinner("L'IA prépare ton CV..."):
            try:
                generator = PersonalCVGenerator()
                # Exécution asynchrone
                result = asyncio.run(generator.generate_cv_for_job(job))
                
                # Mise à jour de la DB
                db.save_generation(job["id"], result.get("pdf_path"), "")
                
                # Sauvegarde dans le session_state
                st.session_state["generated_cv_data"] = result.get("cv_data")
                st.session_state["generation_status"] = "done"
                st.toast("CV Généré avec succès !")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la génération : {e}")
                st.session_state["generation_status"] = "idle"

def render_edit_section(job: dict):
    """Section d'édition du Headline et du Summary."""
    st.markdown("### ✍️ Personnalisation finale")
    
    # Récupération des données (soit du session_state, soit de l'offre en DB)
    cv_data = st.session_state.get("generated_cv_data", {})
    default_headline = job.get("final_headline") or cv_data.get("personal_info", {}).get("headline", "")
    default_summary = job.get("final_summary") or cv_data.get("personal_info", {}).get("summary_default", "")
    
    headline = st.text_area("Accroche (Headline)", value=default_headline, height=70)
    summary = st.text_area("Résumé (Summary)", value=default_summary, height=150)
    
    # Sauvegarde immédiate dans le session_state pour le bloc d'action
    st.session_state["edited_headline"] = headline
    st.session_state["edited_summary"] = summary
