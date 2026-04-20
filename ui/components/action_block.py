"""
Composant d'action pour le Dashboard — Gère les flux de candidature (Voie A & B).
"""

import streamlit as st
from pathlib import Path
from engine.database import JobDatabase

db = JobDatabase()

def render_action_block(job: dict):
    """Rendu du bloc d'action principal."""
    st.markdown("### ⚡ Actions de candidature")
    
    tab_a, tab_b = st.tabs(["🛣️ Voie A : Manuelle", "🤖 Voie B : AIHawk"])
    
    with tab_a:
        render_voie_a(job)
        
    with tab_b:
        render_voie_b(job)

def render_voie_a(job: dict):
    """Flux de candidature manuelle."""
    st.info("Télécharge ton pack et postule directement sur le site de l'entreprise.")
    
    col1, col2 = st.columns(2)
    
    # Bouton de téléchargement du CV
    cv_path = job.get("cv_path")
    if cv_path and Path(cv_path).exists():
        with open(cv_path, "rb") as f:
            st.download_button(
                label="📄 Télécharger mon CV",
                data=f.read(),
                file_name=Path(cv_path).name,
                mime="application/pdf" if cv_path.endswith(".pdf") else "text/markdown",
                use_container_width=True,
                type="primary"
            )
    else:
        st.warning("CV non généré ou introuvable.")
        
    # Lien vers l'offre
    if job.get("url"):
        st.link_button("🌐 Voir l'offre originale", job["url"], use_container_width=True)
    
    st.divider()
    
    # Confirmation d'envoi
    if st.button("✅ J'ai postulé manuellement", use_container_width=True):
        # Récupération des modifications éventuelles depuis le session_state
        edited_headline = st.session_state.get("edited_headline")
        edited_summary = st.session_state.get("edited_summary")
        
        success = db.mark_as_sent(
            job_id=job["id"],
            via="manual",
            edited_headline=edited_headline,
            edited_summary=edited_summary,
            vault_path=job.get("cv_path")
        )
        
        if success:
            st.session_state["application_sent"] = True
            st.toast("Candidature enregistrée ! 🚀")
            st.rerun()
        else:
            st.error("Erreur lors de la mise à jour du statut.")

def render_voie_b(job: dict):
    """Mockup pour la Voie B (AIHawk)."""
    st.markdown("#### Automatisation Premium")
    st.caption("Laisse l'IA postuler pour toi sur LinkedIn, Indeed et plus encore.")
    st.button("🤖 Lancer AIHawk (Bientôt)", disabled=True, use_container_width=True)
