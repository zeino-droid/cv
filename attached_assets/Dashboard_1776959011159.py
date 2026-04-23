"""
Dashboard.py
Studio Dynamique de Candidature — Interface principale Streamlit
"""

import streamlit as st
import json
import os
import uuid
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Studio de Candidature",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS personnalisé
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Import Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* Variables globales */
:root {
    --accent: #1a3a5c;
    --accent-light: #2563eb;
    --surface: #f8fafc;
    --border: #e2e8f0;
    --text-muted: #64748b;
    --success: #059669;
    --warning: #d97706;
}

/* Réinitialisation de base */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Header principal */
.studio-header {
    background: linear-gradient(135deg, #1a3a5c 0%, #2563eb 100%);
    color: white;
    padding: 2rem 2.5rem;
    border-radius: 12px;
    margin-bottom: 2rem;
}
.studio-header h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    margin: 0;
}
.studio-header p {
    opacity: 0.8;
    margin: 0.4rem 0 0 0;
    font-size: 0.95rem;
}

/* Cards des candidatures */
.job-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    margin-bottom: 0.8rem;
    transition: box-shadow 0.2s;
}
.job-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
.job-card .company {
    font-weight: 600;
    color: var(--accent);
    font-size: 1rem;
}
.job-card .title {
    color: #1e293b;
    font-size: 0.9rem;
    margin-top: 0.2rem;
}
.status-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 500;
}
.status-nouvelle { background: #dbeafe; color: #1e40af; }
.status-en_cours { background: #fef3c7; color: #92400e; }
.status-envoyee { background: #d1fae5; color: #065f46; }
.status-refusee { background: #fee2e2; color: #991b1b; }

/* Zone d'édition studio */
.studio-section-header {
    background: #f1f5f9;
    border-left: 4px solid var(--accent-light);
    padding: 0.6rem 1rem;
    border-radius: 0 6px 6px 0;
    font-weight: 600;
    color: var(--accent);
    margin: 1rem 0 0.4rem 0;
    font-size: 0.9rem;
}

/* AI Assistant */
.ai-hint {
    background: linear-gradient(135deg, #eff6ff, #f0fdf4);
    border: 1px solid #93c5fd;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    font-size: 0.82rem;
    color: #1e40af;
    margin-bottom: 0.5rem;
}

/* Boutons d'action */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.2s;
}

/* Tabs */
[data-baseweb="tab"] {
    font-family: 'Inter', sans-serif;
    font-weight: 500;
}

/* Metric cards */
.metric-card {
    background: white;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    text-align: center;
}
.metric-number {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2rem;
    font-weight: 700;
    color: var(--accent);
}
.metric-label {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.2rem;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #f1f5f9; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Import des modules engine (avec gestion d'import gracieuse)
# ---------------------------------------------------------------------------
try:
    from engine.cv_generator import (
        generate_cv_content,
        generate_cover_letter,
        ai_edit_section,
        cv_content_to_typst,
        cover_letter_to_typst,
        compile_typst_to_pdf,
        _load_profile,
    )
    from engine.database import (
        init_db,
        upsert_candidature,
        list_candidatures,
        save_resume_version,
        save_cover_letter_version,
        get_resume_versions,
        get_cover_letter_versions,
        update_candidature_statut,
        update_candidature_url,
        get_archive_stats,
    )
    from engine.link_rescue import check_url_alive, search_fallback_links
    ENGINE_OK = True
except ImportError as e:
    ENGINE_OK = False
    ENGINE_ERROR = str(e)

# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------
if ENGINE_OK:
    init_db()

PROFILE_PATH = os.environ.get("PROFILE_PATH", "master_profile.json")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "output")


def load_profile_safe() -> dict:
    if os.path.exists(PROFILE_PATH):
        return _load_profile(PROFILE_PATH)
    return {}


# ---------------------------------------------------------------------------
# Session State
# ---------------------------------------------------------------------------
def init_session():
    defaults = {
        "current_cv": None,          # dict — contenu CV généré
        "current_letter": None,      # str — texte lettre générée
        "current_cv_typst": None,
        "current_letter_typst": None,
        "current_job_id": None,
        "current_job_offer": None,
        "generation_done": False,
        "cv_pdf_bytes": None,
        "letter_pdf_bytes": None,
        "ai_loading": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()


# ---------------------------------------------------------------------------
# ███████╗████████╗██╗   ██╗██████╗ ██╗ ██████╗
# ██╔════╝╚══██╔══╝██║   ██║██╔══██╗██║██╔═══██╗
# ███████╗   ██║   ██║   ██║██║  ██║██║██║   ██║
# ╚════██║   ██║   ██║   ██║██║  ██║██║██║   ██║
# ███████║   ██║   ╚██████╔╝██████╔╝██║╚██████╔╝
# ╚══════╝   ╚═╝    ╚═════╝ ╚═════╝ ╚═╝ ╚═════╝
# ---------------------------------------------------------------------------

@st.dialog("🎯 Studio de Candidature", width="large")
def generation_studio(job_offer: dict, job_id: str):
    """
    Modale principale du Studio Dynamique.
    Phases : Génération → Visualisation → Édition IA → Export PDF
    """
    profile = load_profile_safe()

    # ---- Onglets principaux ----
    tab_gen, tab_cv, tab_letter, tab_export = st.tabs([
        "⚡ Génération",
        "📄 CV Studio",
        "✉️ Lettre Studio",
        "📦 Export Final",
    ])

    # =========================================================
    # ONGLET 1 — GÉNÉRATION INITIALE
    # =========================================================
    with tab_gen:
        st.markdown(f"""
        <div style='background:#f0f9ff;border:1px solid #93c5fd;border-radius:8px;padding:1rem;margin-bottom:1rem'>
            <strong style='color:#1e40af'>Offre ciblée</strong><br>
            <span style='font-size:1.1rem;font-weight:600'>{job_offer.get('titre', job_offer.get('title', 'Poste'))}</span>
            — {job_offer.get('entreprise', job_offer.get('company', ''))}
        </div>
        """, unsafe_allow_html=True)

        if not ENGINE_OK:
            st.error(f"❌ Modules engine non disponibles : {ENGINE_ERROR}")
            st.code("pip install google-generativeai weasyprint", language="bash")
            return

        if not os.path.exists(PROFILE_PATH):
            st.warning(f"⚠️ Profil non trouvé : `{PROFILE_PATH}`. Veuillez créer votre `master_profile.json`.")
            return

        col1, col2 = st.columns(2)
        with col1:
            gen_cv = st.checkbox("Générer le CV", value=True)
        with col2:
            gen_letter = st.checkbox("Générer la lettre de motivation", value=True)

        if st.button("🚀 Lancer la génération", type="primary", use_container_width=True):
            with st.status("Génération en cours...", expanded=True) as status:
                try:
                    if gen_cv:
                        st.write("🧠 Analyse du profil et de l'offre...")
                        cv_content = generate_cv_content(profile, job_offer)
                        st.session_state.current_cv = cv_content
                        st.write("✅ Contenu CV généré")

                        st.write("📐 Compilation Typst → PDF...")
                        cv_typst = cv_content_to_typst(cv_content, profile)
                        st.session_state.current_cv_typst = cv_typst

                        os.makedirs(OUTPUT_DIR, exist_ok=True)
                        cv_pdf_path = os.path.join(OUTPUT_DIR, f"{job_id}_cv.pdf")
                        ok = compile_typst_to_pdf(cv_typst, cv_pdf_path)
                        if ok:
                            with open(cv_pdf_path, "rb") as f:
                                st.session_state.cv_pdf_bytes = f.read()
                            st.write("✅ PDF CV compilé")
                        else:
                            st.write("⚠️ Typst non installé — PDF indisponible (contenu textuel généré)")

                    if gen_letter:
                        st.write("✍️ Rédaction de la lettre de motivation...")
                        letter_text = generate_cover_letter(profile, job_offer)
                        st.session_state.current_letter = letter_text
                        st.write("✅ Lettre générée")

                        letter_typst = cover_letter_to_typst(letter_text, profile, job_offer)
                        st.session_state.current_letter_typst = letter_typst

                        letter_pdf_path = os.path.join(OUTPUT_DIR, f"{job_id}_letter.pdf")
                        ok = compile_typst_to_pdf(letter_typst, letter_pdf_path)
                        if ok:
                            with open(letter_pdf_path, "rb") as f:
                                st.session_state.letter_pdf_bytes = f.read()
                            st.write("✅ PDF Lettre compilé")

                    # Sauvegarder en base
                    upsert_candidature(job_offer, job_id, statut="en_cours")
                    st.session_state.current_job_id = job_id
                    st.session_state.current_job_offer = job_offer
                    st.session_state.generation_done = True

                    if st.session_state.current_cv:
                        save_resume_version(
                            job_id=job_id,
                            cv_content=st.session_state.current_cv,
                            cv_typst=st.session_state.current_cv_typst or "",
                            cv_pdf_path=os.path.join(OUTPUT_DIR, f"{job_id}_cv.pdf"),
                            is_final=False,
                            notes="Version initiale auto-générée",
                        )
                    if st.session_state.current_letter:
                        save_cover_letter_version(
                            job_id=job_id,
                            letter_text=st.session_state.current_letter,
                            letter_typst=st.session_state.current_letter_typst or "",
                            letter_pdf_path=os.path.join(OUTPUT_DIR, f"{job_id}_letter.pdf"),
                            is_final=False,
                            notes="Version initiale auto-générée",
                        )

                    status.update(label="✅ Génération terminée !", state="complete")
                    st.success("Passez aux onglets **CV Studio** et **Lettre Studio** pour affiner.")

                except Exception as e:
                    status.update(label="❌ Erreur", state="error")
                    st.error(f"Erreur lors de la génération : {e}")

    # =========================================================
    # ONGLET 2 — CV STUDIO
    # =========================================================
    with tab_cv:
        if not st.session_state.current_cv:
            st.info("⚡ Lancez d'abord la génération dans l'onglet **Génération**.")
        else:
            cv = st.session_state.current_cv
            profile = load_profile_safe()

            st.markdown("### 📝 Édition en direct du CV")
            st.markdown(
                '<div class="ai-hint">💡 Modifiez directement le texte dans chaque zone, puis utilisez l\'<strong>Assistant IA</strong> pour des reformulations intelligentes.</div>',
                unsafe_allow_html=True,
            )

            # -- Section : Accroche + Résumé --
            st.markdown('<div class="studio-section-header">🎯 Accroche & Résumé Professionnel</div>', unsafe_allow_html=True)
            cv["accroche"] = st.text_input("Accroche", value=cv.get("accroche", ""))
            cv["resume_professionnel"] = st.text_area(
                "Résumé professionnel", value=cv.get("resume_professionnel", ""), height=100
            )
            _ai_editor_widget("accroche_resume", cv, "accroche + resume_professionnel", profile, job_offer if st.session_state.current_job_offer else {})

            # -- Section : Expériences --
            st.markdown('<div class="studio-section-header">💼 Expériences Professionnelles</div>', unsafe_allow_html=True)
            for i, exp in enumerate(cv.get("experiences", [])):
                with st.expander(f"**{exp.get('poste', 'Poste')}** — {exp.get('entreprise', '')} ({exp.get('periode', '')})", expanded=(i == 0)):
                    exp["poste"] = st.text_input(f"Intitulé du poste", value=exp.get("poste", ""), key=f"exp_poste_{i}")
                    exp["entreprise"] = st.text_input(f"Entreprise", value=exp.get("entreprise", ""), key=f"exp_ent_{i}")
                    col1, col2 = st.columns(2)
                    with col1:
                        exp["periode"] = st.text_input("Période", value=exp.get("periode", ""), key=f"exp_per_{i}")
                    with col2:
                        exp["lieu"] = st.text_input("Lieu", value=exp.get("lieu", ""), key=f"exp_lieu_{i}")

                    missions_text = "\n".join(exp.get("missions", []))
                    new_missions = st.text_area(
                        "Missions (une par ligne)",
                        value=missions_text,
                        height=100,
                        key=f"exp_missions_{i}",
                    )
                    exp["missions"] = [m.strip() for m in new_missions.split("\n") if m.strip()]
                    _ai_editor_widget(f"experience_{i}", exp, f"expérience {exp.get('poste', '')}", profile, st.session_state.current_job_offer or {})

            # -- Section : Compétences --
            st.markdown('<div class="studio-section-header">🛠 Compétences</div>', unsafe_allow_html=True)
            comp = cv.get("competences", {})
            col1, col2 = st.columns(2)
            with col1:
                comp["techniques"] = [
                    s.strip()
                    for s in st.text_area("Compétences techniques (séparées par virgule)", value=", ".join(comp.get("techniques", [])), height=80).split(",")
                    if s.strip()
                ]
                comp["outils"] = [
                    s.strip()
                    for s in st.text_area("Outils (séparées par virgule)", value=", ".join(comp.get("outils", [])), height=80).split(",")
                    if s.strip()
                ]
            with col2:
                comp["langues"] = [
                    s.strip()
                    for s in st.text_area("Langues", value=", ".join(comp.get("langues", [])), height=80).split(",")
                    if s.strip()
                ]
                comp["soft_skills"] = [
                    s.strip()
                    for s in st.text_area("Soft skills", value=", ".join(comp.get("soft_skills", [])), height=80).split(",")
                    if s.strip()
                ]
            cv["competences"] = comp

            # -- Section : Formations --
            st.markdown('<div class="studio-section-header">🎓 Formations</div>', unsafe_allow_html=True)
            for i, form in enumerate(cv.get("formations", [])):
                with st.expander(f"{form.get('diplome', 'Diplôme')} — {form.get('etablissement', '')}", expanded=False):
                    form["diplome"] = st.text_input("Diplôme", value=form.get("diplome", ""), key=f"form_dip_{i}")
                    form["etablissement"] = st.text_input("Établissement", value=form.get("etablissement", ""), key=f"form_etab_{i}")
                    col1, col2 = st.columns(2)
                    with col1:
                        form["periode"] = st.text_input("Période", value=form.get("periode", ""), key=f"form_per_{i}")
                    with col2:
                        form["mention"] = st.text_input("Mention", value=form.get("mention", ""), key=f"form_men_{i}")

            # Mise à jour session state
            st.session_state.current_cv = cv

            # Bouton recompiler
            if st.button("🔄 Recompiler le PDF CV", type="secondary", use_container_width=True):
                with st.spinner("Compilation Typst en cours..."):
                    try:
                        new_typst = cv_content_to_typst(cv, profile)
                        st.session_state.current_cv_typst = new_typst
                        pdf_path = os.path.join(OUTPUT_DIR, f"{st.session_state.current_job_id}_cv_v2.pdf")
                        ok = compile_typst_to_pdf(new_typst, pdf_path)
                        if ok:
                            with open(pdf_path, "rb") as f:
                                st.session_state.cv_pdf_bytes = f.read()
                            st.success("✅ PDF recompilé avec succès !")
                        else:
                            st.warning("⚠️ Typst non disponible — installez-le avec `cargo install typst-cli`")
                    except Exception as e:
                        st.error(f"Erreur : {e}")

    # =========================================================
    # ONGLET 3 — LETTRE STUDIO
    # =========================================================
    with tab_letter:
        if not st.session_state.current_letter:
            st.info("⚡ Lancez d'abord la génération dans l'onglet **Génération**.")
        else:
            profile = load_profile_safe()
            st.markdown("### ✉️ Édition de la Lettre de Motivation")
            st.markdown(
                '<div class="ai-hint">💡 Modifiez le texte directement ou donnez une instruction à l\'Assistant IA pour reformuler un paragraphe spécifique.</div>',
                unsafe_allow_html=True,
            )

            # Éditeur principal
            new_letter = st.text_area(
                "Corps de la lettre",
                value=st.session_state.current_letter,
                height=400,
                key="letter_editor",
            )
            st.session_state.current_letter = new_letter

            # Compteur de mots
            word_count = len(new_letter.split())
            color = "green" if 250 <= word_count <= 350 else "orange" if word_count < 250 else "red"
            st.markdown(f"<small>Mots : <span style='color:{color};font-weight:600'>{word_count}</span> / 250–350 recommandés</small>", unsafe_allow_html=True)

            # Assistant IA global lettre
            st.markdown("---")
            st.markdown("#### 🤖 Assistant IA — Lettre")
            instruction_letter = st.text_input(
                "Instruction de modification",
                placeholder='Ex: "Rends le ton plus enthousiaste" ou "Ajoute une référence à mon expérience en IA"',
                key="ai_letter_instruction",
            )
            if st.button("✨ Appliquer l'instruction IA", key="btn_ai_letter"):
                if instruction_letter:
                    with st.spinner("L'IA rewrite votre lettre..."):
                        try:
                            updated = ai_edit_section(
                                section_name="lettre de motivation",
                                current_content=new_letter,
                                instruction=instruction_letter,
                                profile=profile,
                                job_offer=st.session_state.current_job_offer or {},
                            )
                            st.session_state.current_letter = updated
                            st.success("✅ Lettre mise à jour !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur IA : {e}")
                else:
                    st.warning("Donnez une instruction avant d'appliquer.")

            if st.button("🔄 Recompiler le PDF Lettre", type="secondary", use_container_width=True):
                with st.spinner("Compilation..."):
                    try:
                        new_typst = cover_letter_to_typst(
                            st.session_state.current_letter,
                            profile,
                            st.session_state.current_job_offer or {},
                        )
                        st.session_state.current_letter_typst = new_typst
                        pdf_path = os.path.join(OUTPUT_DIR, f"{st.session_state.current_job_id}_letter_v2.pdf")
                        ok = compile_typst_to_pdf(new_typst, pdf_path)
                        if ok:
                            with open(pdf_path, "rb") as f:
                                st.session_state.letter_pdf_bytes = f.read()
                            st.success("✅ PDF recompilé !")
                        else:
                            st.warning("⚠️ Typst non disponible")
                    except Exception as e:
                        st.error(f"Erreur : {e}")

    # =========================================================
    # ONGLET 4 — EXPORT FINAL
    # =========================================================
    with tab_export:
        st.markdown("### 📦 Finalisation & Export")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📄 CV Final")
            if st.session_state.cv_pdf_bytes:
                st.download_button(
                    label="⬇️ Télécharger le CV (PDF)",
                    data=st.session_state.cv_pdf_bytes,
                    file_name=f"CV_{job_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                )
                if st.button("✅ Marquer comme version finale (CV)", key="final_cv"):
                    if st.session_state.current_cv and st.session_state.current_job_id:
                        save_resume_version(
                            job_id=st.session_state.current_job_id,
                            cv_content=st.session_state.current_cv,
                            cv_typst=st.session_state.current_cv_typst or "",
                            cv_pdf_path=os.path.join(OUTPUT_DIR, f"{job_id}_cv.pdf"),
                            is_final=True,
                            notes="Version finale validée par l'utilisateur",
                        )
                        st.success("✅ Version finale CV enregistrée en base !")
            else:
                st.info("PDF non disponible (Typst requis)")

        with col2:
            st.markdown("#### ✉️ Lettre Finale")
            if st.session_state.letter_pdf_bytes:
                st.download_button(
                    label="⬇️ Télécharger la Lettre (PDF)",
                    data=st.session_state.letter_pdf_bytes,
                    file_name=f"Lettre_{job_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                )
                if st.button("✅ Marquer comme version finale (Lettre)", key="final_letter"):
                    if st.session_state.current_letter and st.session_state.current_job_id:
                        save_cover_letter_version(
                            job_id=st.session_state.current_job_id,
                            letter_text=st.session_state.current_letter,
                            letter_typst=st.session_state.current_letter_typst or "",
                            letter_pdf_path=os.path.join(OUTPUT_DIR, f"{job_id}_letter.pdf"),
                            is_final=True,
                            notes="Version finale validée par l'utilisateur",
                        )
                        st.success("✅ Version finale Lettre enregistrée en base !")
            else:
                if st.session_state.current_letter:
                    st.download_button(
                        label="⬇️ Télécharger la Lettre (.txt)",
                        data=st.session_state.current_letter.encode("utf-8"),
                        file_name=f"Lettre_{job_id}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

        # Mise à jour du statut
        st.markdown("---")
        st.markdown("#### 📊 Statut de la candidature")
        new_statut = st.selectbox(
            "Mettre à jour le statut",
            ["nouvelle", "en_cours", "envoyee", "relance", "entretien", "refusee", "acceptee"],
            index=2,
            key="statut_selector",
        )
        if st.button("💾 Sauvegarder le statut", use_container_width=True):
            if st.session_state.current_job_id:
                update_candidature_statut(st.session_state.current_job_id, new_statut)
                st.success(f"✅ Statut mis à jour : **{new_statut}**")

        # Lien de secours
        st.markdown("---")
        st.markdown("#### 🔗 Lien de Secours (offre expirée)")
        original_url = job_offer.get("url", "")
        is_alive = check_url_alive(original_url) if original_url else False
        if original_url:
            if is_alive:
                st.success(f"✅ Lien original actif : [{original_url}]({original_url})")
            else:
                st.warning("⚠️ Le lien original semble expiré. Liens de secours :")
                fallbacks = search_fallback_links(job_offer)
                for fb in fallbacks[:4]:
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        st.markdown(f"🔗 [{fb['title']}]({fb['url']})")
                        if fb.get("snippet"):
                            st.caption(fb["snippet"])
                    with col_b:
                        if st.button("📌 Utiliser ce lien", key=f"use_link_{fb['url'][:20]}"):
                            if st.session_state.current_job_id:
                                update_candidature_url(st.session_state.current_job_id, fb["url"])
                                st.success("Lien mis à jour !")


def _ai_editor_widget(section_key: str, section_data, section_label: str, profile: dict, job_offer: dict):
    """Widget réutilisable pour l'assistant IA par section."""
    with st.expander(f"🤖 Assistant IA — {section_label}", expanded=False):
        instruction = st.text_input(
            "Instruction",
            placeholder='Ex: "Rends ça plus orienté management" ou "Ajoute le projet hydrogène"',
            key=f"ai_instruction_{section_key}",
        )
        if st.button("✨ Appliquer", key=f"ai_apply_{section_key}", type="secondary"):
            if instruction:
                with st.spinner("Réécriture IA en cours..."):
                    try:
                        content_str = json.dumps(section_data, ensure_ascii=False) if isinstance(section_data, dict) else str(section_data)
                        result = ai_edit_section(
                            section_name=section_label,
                            current_content=content_str,
                            instruction=instruction,
                            profile=profile,
                            job_offer=job_offer,
                        )
                        st.success("✅ Suggestion IA :")
                        st.info(result)
                        st.caption("Copiez-collez le résultat dans le champ concerné.")
                    except Exception as e:
                        st.error(f"Erreur IA : {e}")
            else:
                st.warning("Entrez une instruction.")


# ---------------------------------------------------------------------------
# ██████╗  █████╗ ███████╗██╗  ██╗██████╗  ██████╗  █████╗ ██████╗ ██████╗
# ██╔══██╗██╔══██╗██╔════╝██║  ██║██╔══██╗██╔═══██╗██╔══██╗██╔══██╗██╔══██╗
# ██║  ██║███████║███████╗███████║██████╔╝██║   ██║███████║██████╔╝██║  ██║
# ██║  ██║██╔══██║╚════██║██╔══██║██╔══██╗██║   ██║██╔══██║██╔══██╗██║  ██║
# ██████╔╝██║  ██║███████║██║  ██║██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝
# ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
# ---------------------------------------------------------------------------

# Header
st.markdown("""
<div class="studio-header">
    <h1>🎯 Studio de Candidature</h1>
    <p>Générez, affinez et exportez vos dossiers de candidature avec l'IA</p>
</div>
""", unsafe_allow_html=True)

# Navigation sidebar
with st.sidebar:
    st.markdown("### 🗂 Navigation")
    page = st.radio(
        "",
        ["🏠 Tableau de bord", "➕ Nouvelle candidature", "📚 Archives", "⚙️ Profil"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    if ENGINE_OK:
        stats = get_archive_stats() if ENGINE_OK else {}
        st.markdown(f"**{stats.get('total_candidatures', 0)}** candidatures")
        st.markdown(f"**{stats.get('cv_finaux', 0)}** CV finaux")
        st.markdown(f"**{stats.get('lettres_finales', 0)}** Lettres finales")


# =========================================================
# PAGE : TABLEAU DE BORD
# =========================================================
if "Tableau de bord" in page:
    if not ENGINE_OK:
        st.error(f"❌ Erreur import modules : {ENGINE_ERROR}")
        st.code("pip install google-generativeai", language="bash")
    else:
        candidatures = list_candidatures()

        if not candidatures:
            st.markdown("""
            <div style='text-align:center;padding:3rem;color:#94a3b8'>
                <div style='font-size:3rem'>📭</div>
                <h3>Aucune candidature pour le moment</h3>
                <p>Commencez par créer une nouvelle candidature.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Métriques
            stats = get_archive_stats()
            col1, col2, col3, col4 = st.columns(4)
            for col, (num, label) in zip(
                [col1, col2, col3, col4],
                [
                    (stats["total_candidatures"], "Candidatures"),
                    (stats["par_statut"].get("envoyee", 0), "Envoyées"),
                    (stats["par_statut"].get("entretien", 0), "Entretiens"),
                    (stats["cv_finaux"], "CV Finaux"),
                ],
            ):
                with col:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-number">{num}</div>
                        <div class="metric-label">{label}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### Mes Candidatures")

            # Filtre par statut
            filter_statut = st.selectbox("Filtrer par statut", ["Tous", "nouvelle", "en_cours", "envoyee", "entretien", "refusee"], key="filter_dash")

            filtered = candidatures if filter_statut == "Tous" else [c for c in candidatures if c["statut"] == filter_statut]

            for cand in filtered:
                job_offer_data = json.loads(cand["job_offer_json"]) if cand.get("job_offer_json") else {}

                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                    with col1:
                        st.markdown(f"**{cand['poste']}**")
                        st.caption(cand["entreprise"])
                    with col2:
                        st.caption(f"📅 {cand['date_creation'][:10] if cand.get('date_creation') else 'N/A'}")
                    with col3:
                        statut_classes = {
                            "nouvelle": "status-nouvelle",
                            "en_cours": "status-en_cours",
                            "envoyee": "status-envoyee",
                            "refusee": "status-refusee",
                        }
                        css_class = statut_classes.get(cand["statut"], "status-nouvelle")
                        st.markdown(f'<span class="status-badge {css_class}">{cand["statut"]}</span>', unsafe_allow_html=True)
                    with col4:
                        if st.button("🎨 Studio", key=f"open_studio_{cand['job_id']}"):
                            generation_studio(job_offer_data, cand["job_id"])
                    st.divider()


# =========================================================
# PAGE : NOUVELLE CANDIDATURE
# =========================================================
elif "Nouvelle candidature" in page:
    st.markdown("### ➕ Nouvelle Candidature")

    with st.form("new_job_form"):
        st.markdown("#### Informations sur l'offre")
        col1, col2 = st.columns(2)
        with col1:
            titre = st.text_input("Intitulé du poste *", placeholder="Ex: Ingénieur Data Science")
            entreprise = st.text_input("Entreprise *", placeholder="Ex: TotalEnergies")
            localisation = st.text_input("Localisation", placeholder="Ex: Paris, Ile-de-France")
        with col2:
            type_contrat = st.selectbox("Type de contrat", ["CDI", "CDD", "Stage", "Alternance", "Freelance", "Autre"])
            url_offre = st.text_input("URL de l'offre", placeholder="https://...")
            date_limite = st.date_input("Date limite (optionnel)", value=None)

        description = st.text_area(
            "Description de l'offre *",
            placeholder="Collez ici la description complète du poste...",
            height=200,
        )

        competences_requises = st.text_area(
            "Compétences requises (optionnel)",
            placeholder="Ex: Python, Machine Learning, SQL, Gestion de projet...",
            height=80,
        )

        submitted = st.form_submit_button("🚀 Créer et ouvrir le Studio", type="primary", use_container_width=True)

    if submitted:
        if not titre or not entreprise or not description:
            st.error("❌ Veuillez remplir les champs obligatoires (Poste, Entreprise, Description).")
        else:
            job_id = f"{entreprise.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
            job_offer = {
                "titre": titre,
                "entreprise": entreprise,
                "localisation": localisation,
                "type_contrat": type_contrat,
                "url": url_offre,
                "description": description,
                "competences_requises": [c.strip() for c in competences_requises.split(",") if c.strip()],
                "date_limite": str(date_limite) if date_limite else "",
            }

            # Réinitialiser le state pour une nouvelle génération
            for k in ["current_cv", "current_letter", "current_cv_typst", "current_letter_typst",
                      "cv_pdf_bytes", "letter_pdf_bytes", "generation_done"]:
                st.session_state[k] = None if k != "generation_done" else False

            generation_studio(job_offer, job_id)


# =========================================================
# PAGE : ARCHIVES
# =========================================================
elif "Archives" in page:
    st.markdown("### 📚 Archives des Candidatures")

    if not ENGINE_OK:
        st.error("Modules non disponibles")
    else:
        candidatures = list_candidatures()
        if not candidatures:
            st.info("Aucune candidature archivée.")
        else:
            for cand in candidatures:
                job_offer_data = json.loads(cand["job_offer_json"]) if cand.get("job_offer_json") else {}
                with st.expander(f"**{cand['poste']}** @ {cand['entreprise']} — {cand['statut']}", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Job ID :** `{cand['job_id']}`")
                        st.markdown(f"**Créé le :** {cand['date_creation'][:16] if cand.get('date_creation') else 'N/A'}")
                        st.markdown(f"**Modifié :** {cand['date_modification'][:16] if cand.get('date_modification') else 'N/A'}")
                        if cand.get("url_offre"):
                            st.markdown(f"**Offre :** [{cand['url_offre'][:50]}...]({cand['url_offre']})")

                    with col2:
                        # Versions CV
                        cv_versions = get_resume_versions(cand["job_id"])
                        letter_versions = get_cover_letter_versions(cand["job_id"])
                        st.markdown(f"**Versions CV :** {len(cv_versions)}")
                        st.markdown(f"**Versions Lettre :** {len(letter_versions)}")

                        cv_finals = [v for v in cv_versions if v["is_final"]]
                        if cv_finals:
                            pdf_path = cv_finals[0].get("cv_pdf_path", "")
                            if pdf_path and os.path.exists(pdf_path):
                                with open(pdf_path, "rb") as f:
                                    st.download_button(
                                        "⬇️ CV Final PDF",
                                        data=f.read(),
                                        file_name=f"CV_{cand['job_id']}.pdf",
                                        mime="application/pdf",
                                        key=f"dl_cv_{cand['job_id']}",
                                    )

                        letter_finals = [v for v in letter_versions if v["is_final"]]
                        if letter_finals:
                            letter_pdf = letter_finals[0].get("letter_pdf_path", "")
                            if letter_pdf and os.path.exists(letter_pdf):
                                with open(letter_pdf, "rb") as f:
                                    st.download_button(
                                        "⬇️ Lettre Finale PDF",
                                        data=f.read(),
                                        file_name=f"Lettre_{cand['job_id']}.pdf",
                                        mime="application/pdf",
                                        key=f"dl_letter_{cand['job_id']}",
                                    )

                    if st.button(f"🎨 Rouvrir le Studio", key=f"archive_studio_{cand['job_id']}"):
                        generation_studio(job_offer_data, cand["job_id"])


# =========================================================
# PAGE : PROFIL
# =========================================================
elif "Profil" in page:
    st.markdown("### ⚙️ Profil Candidat")

    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            profile_content = f.read()

        st.success(f"✅ Profil chargé depuis `{PROFILE_PATH}`")
        edited_profile = st.text_area(
            "Éditer le profil (JSON)",
            value=profile_content,
            height=500,
        )
        if st.button("💾 Sauvegarder le profil", type="primary"):
            try:
                json.loads(edited_profile)  # Validation JSON
                with open(PROFILE_PATH, "w", encoding="utf-8") as f:
                    f.write(edited_profile)
                st.success("✅ Profil sauvegardé !")
            except json.JSONDecodeError as e:
                st.error(f"❌ JSON invalide : {e}")
    else:
        st.warning(f"Fichier `{PROFILE_PATH}` introuvable.")
        st.markdown("Créez votre `master_profile.json` avec la structure suivante :")
        st.code(json.dumps({
            "nom": "Prénom Nom",
            "contact": {
                "email": "email@example.com",
                "telephone": "+33 6 00 00 00 00",
                "localisation": "Paris, France",
                "linkedin": "linkedin.com/in/prenom-nom",
                "github": "github.com/prenom-nom",
            },
            "experiences": [],
            "formations": [],
            "competences": {
                "techniques": [],
                "outils": [],
                "langues": [],
                "soft_skills": [],
            },
            "projets": [],
            "certifications": [],
        }, indent=2, ensure_ascii=False), language="json")
        
        if st.button("📋 Créer un profil vide"):
            profile_template = {
                "nom": "Prénom Nom",
                "contact": {
                    "email": "email@example.com",
                    "telephone": "+33 6 00 00 00 00",
                    "localisation": "Paris, France",
                    "ville": "Paris",
                    "linkedin": "",
                    "github": "",
                },
                "experiences": [
                    {
                        "poste": "Exemple de poste",
                        "entreprise": "Entreprise",
                        "periode": "2022 - Présent",
                        "lieu": "Paris",
                        "missions": ["Mission 1", "Mission 2"],
                    }
                ],
                "formations": [
                    {
                        "diplome": "Master Exemple",
                        "etablissement": "Université",
                        "periode": "2020 - 2022",
                        "mention": "Très Bien",
                    }
                ],
                "competences": {
                    "techniques": ["Python", "Machine Learning"],
                    "outils": ["Git", "Docker"],
                    "langues": ["Français (natif)", "Anglais (C1)"],
                    "soft_skills": ["Leadership", "Communication"],
                },
                "projets": [],
                "certifications": [],
                "centres_interet": ["Innovation", "Sport"],
            }
            with open(PROFILE_PATH, "w", encoding="utf-8") as f:
                json.dump(profile_template, f, ensure_ascii=False, indent=2)
            st.success(f"✅ Profil créé : `{PROFILE_PATH}`. Éditez-le maintenant.")
            st.rerun()
