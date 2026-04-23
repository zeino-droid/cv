# 🎯 Job Copilot — Plan de Développement : Studio Dynamique
**Basé sur l'analyse du repo `zeino-droid/cv` (Pipeline.py + Dashboard.py)**  
*Document technique — Sprints détaillés avec modifications de code spécifiques*

---

## Vue d'ensemble de l'architecture cible

```
Dashboard.py (st.dialog "Studio")
├── Onglet 1 — 🔬 Analyse       → Heatmap compétences (Profil ↔ Offre)
├── Onglet 2 — ✏️  Édition Live  → st.text_area CV summary + corps lettre
├── Onglet 3 — 🤖 Copilote IA   → Champ commande LLM → réécriture ciblée
└── Bouton "🚀 Générer PDF"
         │
         ├─→ inject edited_summary → cv_generator.generate_cv_for_job()
         ├─→ inject edited_letter  → Pipeline.save_cover_letter()
         └─→ db.save_generation()  (chemins inchangés)
```

**Règle d'or :** Zéro modification destructive de la DB, zéro modèle local chargé, tout passe par les APIs Gemini/Groq existantes.

---

## Sprint 0 — Hygiène des données & Robustesse des liens
**Durée estimée : 2-3h | Fichiers : `engine/database.py`, `Dashboard.py`**

### 0.1 — Fonction de suppression dans `database.py`

Ajouter après la méthode `update_status` existante :

```python
# engine/database.py — AJOUT (non destructif, nouvelle méthode)

def delete_job(self, job_id: str) -> bool:
    """Supprime définitivement une offre et ses fichiers associés."""
    with self._connect() as conn:
        row = conn.execute(
            "SELECT cv_path, letter_path FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if not row:
            return False
        # Nettoyage optionnel des fichiers générés
        for path_col in (row["cv_path"], row["letter_path"]):
            if path_col:
                p = Path(path_col)
                if p.exists():
                    p.unlink(missing_ok=True)
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return True

def delete_jobs_bulk(self, job_ids: list[str]) -> int:
    """Suppression en masse. Retourne le nombre de lignes supprimées."""
    if not job_ids:
        return 0
    placeholders = ",".join("?" * len(job_ids))
    with self._connect() as conn:
        cur = conn.execute(
            f"DELETE FROM jobs WHERE id IN ({placeholders})", job_ids
        )
        return cur.rowcount
```

### 0.2 — Filtres par date et ville dans `get_jobs()`

Modifier la signature de `get_jobs()` pour accepter `date_from` :

```python
# engine/database.py — MODIFICATION de la méthode get_jobs()
# Ajouter le paramètre date_from (compatible avec l'API existante)

def get_jobs(
    self,
    status: str | None = None,
    min_score: int = 0,
    location_filter: str | None = None,
    search: str | None = None,
    limit: int = 100,
    date_from: str | None = None,   # ← NOUVEAU (format ISO "YYYY-MM-DD")
) -> list[dict]:
    query = "SELECT * FROM jobs WHERE fit_score >= ?"
    params: list = [min_score]
    if status:
        query += " AND status = ?"
        params.append(status)
    if location_filter:
        query += " AND location LIKE ?"
        params.append(f"%{location_filter}%")
    if search:
        query += " AND (title LIKE ? OR company LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if date_from:                          # ← NOUVEAU
        query += " AND date_added >= ?"
        params.append(date_from)
    query += " ORDER BY fit_score DESC LIMIT ?"
    params.append(limit)
    # ... reste identique
```

### 0.3 — Lien de secours Google dans `Dashboard.py`

Dans la page `📋 Offres`, remplacer le `st.link_button` existant :

```python
# Dashboard.py — PAGE OFFRES — Remplacement du bloc URL

def _fallback_google_url(job: dict) -> str:
    """Génère une URL de recherche Google si l'URL originale est morte."""
    from urllib.parse import quote_plus
    query = quote_plus(f"{job.get('title','')} {job.get('company','')} emploi")
    return f"https://www.google.com/search?q={query}"

# Dans la boucle d'affichage des offres :
if job.get("url"):
    col_url1, col_url2 = st.columns(2)
    with col_url1:
        st.link_button("🌐 Offre originale", job["url"], use_container_width=True)
    with col_url2:
        st.link_button(
            "🔍 Recherche Google",
            _fallback_google_url(job),
            use_container_width=True,
        )
else:
    st.link_button(
        "🔍 Trouver sur Google",
        _fallback_google_url(job),
        use_container_width=True,
    )
```

---

## Sprint 1 — Module Analyse : Heatmap Compétences
**Durée estimée : 3h | Fichier : `Dashboard.py` (nouveau `@st.dialog`)**

### 1.1 — Nouveau fichier `engine/studio_analysis.py`

Créer ce module léger (pas de modèle local) :

```python
# engine/studio_analysis.py — NOUVEAU FICHIER

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

def build_skill_matrix(profile: dict, job: dict) -> dict:
    """
    Compare les compétences du profil et de l'offre.
    Retourne un dict prêt pour l'affichage Streamlit.
    """
    # Compétences du profil (toutes sources)
    profile_skills: set[str] = set()
    for exp in profile.get("experience_stark", []):
        profile_skills.update(k.lower() for k in exp.get("K", []))
    for edu in profile.get("education", []):
        profile_skills.update(k.lower() for k in edu.get("skills", []))

    # Compétences de l'offre
    required = {s.lower() for s in job.get("required_skills", []) or []}
    matched  = {s.lower() for s in job.get("matched_skills",  []) or []}
    all_job_skills = required | matched

    result = {
        "matched":   sorted(all_job_skills & profile_skills),
        "missing":   sorted(all_job_skills - profile_skills),
        "bonus":     sorted(profile_skills - all_job_skills),
        "score":     job.get("fit_score", 0),
        "total_job": len(all_job_skills),
    }
    return result

def render_heatmap_html(matrix: dict) -> str:
    """Génère un bloc HTML/CSS pour la heatmap — pas de dépendance externe."""
    def pill(skill: str, color: str, bg: str) -> str:
        return (
            f'<span style="display:inline-block;margin:3px;padding:4px 10px;'
            f'border-radius:999px;font-size:0.8rem;font-weight:600;'
            f'color:{color};background:{bg};border:1px solid {color}55;">'
            f'{skill}</span>'
        )

    matched_html = "".join(pill(s, "#4ade80", "rgba(34,197,94,0.1)") for s in matrix["matched"])
    missing_html = "".join(pill(s, "#f87171", "rgba(239,68,68,0.1)")  for s in matrix["missing"])
    bonus_html   = "".join(pill(s, "#60a5fa", "rgba(96,165,250,0.1)") for s in matrix["bonus"][:10])

    score = matrix["score"]
    total = matrix["total_job"] or 1
    match_pct = round(len(matrix["matched"]) / total * 100) if total else 0

    return f"""
    <div style="font-family:'Outfit',sans-serif;">
      <div style="display:flex;gap:24px;margin-bottom:16px;">
        <div style="flex:1;background:rgba(34,197,94,0.08);border-radius:12px;padding:16px;border:1px solid rgba(34,197,94,0.2);">
          <div style="font-size:1.8rem;font-weight:800;color:#4ade80;">{len(matrix['matched'])}</div>
          <div style="font-size:0.8rem;color:#94a3b8;">Compétences matchées</div>
        </div>
        <div style="flex:1;background:rgba(239,68,68,0.08);border-radius:12px;padding:16px;border:1px solid rgba(239,68,68,0.2);">
          <div style="font-size:1.8rem;font-weight:800;color:#f87171;">{len(matrix['missing'])}</div>
          <div style="font-size:0.8rem;color:#94a3b8;">Compétences manquantes</div>
        </div>
        <div style="flex:1;background:rgba(56,189,248,0.08);border-radius:12px;padding:16px;border:1px solid rgba(56,189,248,0.2);">
          <div style="font-size:1.8rem;font-weight:800;color:#38bdf8;">{score}%</div>
          <div style="font-size:0.8rem;color:#94a3b8;">Score global Fit</div>
        </div>
      </div>
      <div style="margin-bottom:16px;">
        <div style="font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">✅ Maîtrisées</div>
        <div>{matched_html or '<span style="color:#475569;font-size:0.8rem;">Aucune détectée</span>'}</div>
      </div>
      <div style="margin-bottom:16px;">
        <div style="font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">⚠️ À mentionner / Lacunes</div>
        <div>{missing_html or '<span style="color:#475569;font-size:0.8rem;">Parfait match !</span>'}</div>
      </div>
      <div>
        <div style="font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">💡 Compétences bonus (non demandées)</div>
        <div>{bonus_html}</div>
      </div>
    </div>
    """
```

---

## Sprint 2 — Module Édition Live (cœur du Studio)
**Durée estimée : 4h | Fichier : `Dashboard.py`**

### 2.1 — Le `@st.dialog` Studio

Remplacer la page `⚡ Générer` actuelle par un dialog plein écran. Dans `Dashboard.py`, ajouter **avant** le bloc `if page == "⚡ Générer":` :

```python
# Dashboard.py — NOUVEAU DIALOG (insérer vers ligne 60, après les imports)

@st.dialog("🎨 Studio de Candidature", width="large")
def open_studio(job: dict, profile: dict):
    """
    Interface scindée en 3 onglets :
    - Analyse    : Heatmap compétences
    - Édition    : text_area CV summary + lettre
    - Copilote   : commande IA
    """
    from engine.studio_analysis import build_skill_matrix, render_heatmap_html

    st.markdown(
        f"### {job['title']} · {job.get('company','?')} "
        f"<span style='font-size:0.9rem;color:#94a3b8;'>— {job.get('location','?')}</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    tab_analyse, tab_edit, tab_copilot = st.tabs(
        ["🔬 Analyse", "✏️ Édition Live", "🤖 Copilote IA"]
    )

    # ── TAB 1 : ANALYSE ────────────────────────────────────────
    with tab_analyse:
        matrix = build_skill_matrix(profile, job)
        st.components.v1.html(render_heatmap_html(matrix), height=420, scrolling=False)

        # Conseil auto-généré
        if matrix["missing"]:
            top_missing = ", ".join(matrix["missing"][:3])
            st.info(
                f"💡 **Conseil** : Mentionne explicitement **{top_missing}** "
                f"dans ton résumé pour booster le score ATS."
            )

    # ── TAB 2 : ÉDITION LIVE ───────────────────────────────────
    with tab_edit:
        # Pré-remplissage intelligent depuis le profil
        default_summary = (
            profile.get("personal_info", {}).get("summary_default", "")
            or "Ingénieur R&D avec expertise en simulation numérique et modélisation."
        )

        # Générer une lettre par défaut (heuristique, rapide, sans LLM)
        if "studio_letter_draft" not in st.session_state:
            from Pipeline import generate_cover_letter_heuristic
            st.session_state["studio_letter_draft"] = generate_cover_letter_heuristic(
                profile, job
            )

        col_cv, col_letter = st.columns(2)

        with col_cv:
            st.markdown("#### 📄 Résumé du CV")
            st.caption("Ce texte sera injecté dans le header Typst.")
            edited_summary = st.text_area(
                "summary",
                value=st.session_state.get("studio_summary_draft", default_summary),
                height=200,
                label_visibility="collapsed",
                key="studio_summary_area",
            )
            st.session_state["studio_summary_draft"] = edited_summary
            char_count = len(edited_summary)
            color = "#4ade80" if char_count <= 400 else "#f87171"
            st.markdown(
                f'<span style="font-size:0.75rem;color:{color};">'
                f'{char_count}/400 caractères recommandés</span>',
                unsafe_allow_html=True,
            )

        with col_letter:
            st.markdown("#### ✉️ Lettre de motivation")
            st.caption("Corps complet, exporté en .txt avec le PDF.")
            edited_letter = st.text_area(
                "letter",
                value=st.session_state.get("studio_letter_draft", ""),
                height=200,
                label_visibility="collapsed",
                key="studio_letter_area",
            )
            st.session_state["studio_letter_draft"] = edited_letter

    # ── TAB 3 : COPILOTE IA ────────────────────────────────────
    with tab_copilot:
        st.markdown("#### 🤖 Commande au Copilote")
        st.caption(
            "Exemples : *Rends l'intro plus dynamique* · "
            "*Ajoute une référence à Python et CFD* · "
            "*Reformule le 2e paragraphe en tutoyant*"
        )

        target = st.radio(
            "Cible",
            ["Résumé CV", "Lettre complète", "Introduction lettre uniquement"],
            horizontal=True,
        )
        command = st.text_input(
            "Instruction",
            placeholder="Ex: Rends l'introduction plus dynamique et orientée résultats",
        )

        if st.button("⚡ Appliquer la commande IA", type="primary"):
            if not command:
                st.warning("Tape une instruction d'abord.")
            else:
                with st.spinner("Le Copilote réécrit..."):
                    result = _copilot_rewrite(
                        target=target,
                        command=command,
                        current_summary=st.session_state.get("studio_summary_draft", ""),
                        current_letter=st.session_state.get("studio_letter_draft", ""),
                        job=job,
                        profile=profile,
                    )
                    if result:
                        if target == "Résumé CV":
                            st.session_state["studio_summary_draft"] = result
                        else:
                            st.session_state["studio_letter_draft"] = result
                        st.success("✅ Copilote a réécrit le texte. Va dans **✏️ Édition Live** pour voir le résultat.")
                        st.rerun()

    # ── BOUTON GÉNÉRATION FINALE ───────────────────────────────
    st.divider()
    col_gen1, col_gen2, col_gen3 = st.columns([2, 1, 1])

    with col_gen1:
        gen_cv     = st.checkbox("📄 CV PDF (Typst)", value=True)
        gen_letter = st.checkbox("✉️ Lettre de motivation", value=True)

    with col_gen2:
        if st.button("🚀 GÉNÉRER LES FICHIERS", type="primary", use_container_width=True):
            _run_generation(
                job=job,
                profile=profile,
                gen_cv=gen_cv,
                gen_letter=gen_letter,
                edited_summary=st.session_state.get("studio_summary_draft"),
                edited_letter=st.session_state.get("studio_letter_draft"),
            )

    with col_gen3:
        if st.button("❌ Annuler", use_container_width=True):
            st.rerun()
```

---

## Sprint 3 — Flux de données : Éditeur → Typst
**Durée estimée : 3h | Fichiers : `engine/cv_generator.py`, `Dashboard.py`**

### 3.1 — Injection dans `cv_generator.py`

La méthode `generate_cv_for_job` accepte déjà `headline_override` et `summary_override` (visible dans `Dashboard.py` ligne ~1060). Il faut s'assurer que le template Typst les utilise correctement.

```python
# engine/cv_generator.py — VÉRIFIER / COMPLÉTER la méthode

async def generate_cv_for_job(
    self,
    job: dict,
    headline_override: str | None = None,
    summary_override: str | None = None,   # ← déjà présent selon Dashboard.py
) -> dict:
    # ... logique existante ...

    # Point d'injection : avant la compilation Typst
    cv_data = self._build_cv_data(job, profile)

    if summary_override and summary_override.strip():
        cv_data["personal_info"]["summary"] = summary_override.strip()

    if headline_override and headline_override.strip():
        cv_data["personal_info"]["headline"] = headline_override.strip()

    # Passer cv_data enrichi à la compilation Typst
    return await self._compile_typst(cv_data)
```

### 3.2 — Architecture du flux données complet

```
st.session_state["studio_summary_draft"]  (str, édité par user ou copilote)
         │
         ▼
open_studio() → _run_generation(edited_summary=...)
         │
         ▼
cv_generator.generate_cv_for_job(summary_override=edited_summary)
         │
         ▼
cv_data["personal_info"]["summary"] = edited_summary
         │
         ▼
Typst template : #set text → {{summary}} → PDF compilé

st.session_state["studio_letter_draft"]   (str, édité par user ou copilote)
         │
         ▼
_run_generation(edited_letter=...)
         │
         ▼
Pipeline.save_cover_letter(letter_text=edited_letter, ...)
         │
         ▼
vault/{company}_{title}/lettre.txt
```

### 3.3 — Fonctions helper dans `Dashboard.py`

```python
# Dashboard.py — NOUVELLES FONCTIONS HELPER (ajouter vers ligne 90)

def _copilot_rewrite(
    target: str,
    command: str,
    current_summary: str,
    current_letter: str,
    job: dict,
    profile: dict,
) -> str | None:
    """
    Appelle le LLM (Gemini via cv_generator) pour réécrire un texte ciblé.
    Aucun modèle local — 100% API.
    """
    import asyncio

    if target == "Résumé CV":
        current_text = current_summary
        context_hint = "résumé de CV (3-4 lignes max, orienté ATS)"
    elif target == "Introduction lettre uniquement":
        lines = current_letter.split("\n\n")
        current_text = lines[2] if len(lines) > 2 else current_letter[:400]
        context_hint = "premier paragraphe d'une lettre de motivation"
    else:
        current_text = current_letter
        context_hint = "lettre de motivation complète"

    prompt = f"""Tu es un expert en rédaction de candidatures pour ingénieurs en France.

TEXTE ACTUEL ({context_hint}) :
{current_text}

POSTE CIBLÉ : {job.get('title','')} chez {job.get('company','')}
COMPÉTENCES CLÉ : {', '.join(job.get('matched_skills',[])[:5])}

INSTRUCTION DE L'UTILISATEUR : {command}

RÈGLES :
- Garde la même structure si pas précisé autrement
- Reste professionnel, en français
- N'ajoute PAS "Voici le texte réécrit :" ou tout préambule
- Réponds UNIQUEMENT avec le texte réécrit, rien d'autre
"""

    async def _call_llm():
        try:
            from engine.cv_generator import PersonalCVGenerator
            gen = PersonalCVGenerator()
            if hasattr(gen, "llm") and gen.llm:
                return await gen.llm.generate(prompt, temperature=0.4)
        except Exception as e:
            st.error(f"Erreur LLM : {e}")
        return None

    return run_coroutine_sync(_call_llm(), context="copilot rewrite")


def _run_generation(
    job: dict,
    profile: dict,
    gen_cv: bool,
    gen_letter: bool,
    edited_summary: str | None,
    edited_letter: str | None,
) -> None:
    """
    Orchestre la génération finale avec les textes édités.
    Mutualise le code existant de la page ⚡ Générer.
    """
    with st.spinner("🚀 Génération en cours..."):
        try:
            cv_result: dict = {}

            if gen_cv:
                from engine.cv_generator import PersonalCVGenerator
                gen_obj = PersonalCVGenerator()
                cv_result = run_coroutine_sync(
                    gen_obj.generate_cv_for_job(
                        job,
                        summary_override=edited_summary,
                    ),
                    context="CV generation",
                )

            letter_path = ""
            if gen_letter and edited_letter:
                from Pipeline import save_cover_letter
                personal_info = profile.get("personal_info", {})
                out_dir = ROOT / "output" / (
                    "".join(c if c.isalnum() or c in "._-" else "_"
                            for c in f"{job.get('company','job')}_{job.get('title','cv')}")[:60]
                )
                lp = save_cover_letter(
                    edited_letter,
                    out_dir,
                    personal_info.get("name", "Candidat"),
                    job.get("company", "Entreprise"),
                    job.get("title", "Poste"),
                )
                letter_path = str(lp)

            cv_path = cv_result.get("pdf_path") or cv_result.get("markdown") or ""
            db.save_generation(job["id"], cv_path, letter_path)

            st.success("✅ Candidature générée avec tes textes personnalisés !")

            if cv_result.get("pdf_path"):
                with open(cv_result["pdf_path"], "rb") as f:
                    st.download_button(
                        "⬇️ Télécharger le CV (PDF)",
                        f,
                        file_name=f"CV_{job.get('company','_')}_{job.get('title','_')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            if letter_path:
                with open(letter_path, "r", encoding="utf-8") as f:
                    st.download_button(
                        "⬇️ Télécharger la Lettre (.txt)",
                        f.read(),
                        file_name=f"Lettre_{job.get('company','_')}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

            # Nettoyage session
            for key in ["studio_summary_draft", "studio_letter_draft"]:
                st.session_state.pop(key, None)

        except Exception as e:
            st.error(f"❌ Erreur de génération : {e}")
            import traceback
            st.code(traceback.format_exc())
```

---

## Sprint 4 — Intégration dans le Dashboard & Points d'entrée
**Durée estimée : 1h | Fichier : `Dashboard.py`**

### 4.1 — Déclencher le Studio depuis la page Offres

Dans la page `📋 Offres`, remplacer le bouton `⚡ Générer CV + Lettre` :

```python
# Dashboard.py — PAGE OFFRES — Remplacement du bouton de génération (vers ligne 1150)

# AVANT :
# if st.button("⚡ Générer CV + Lettre", ...):
#     st.session_state["generate_job"] = job
#     st.session_state["page"] = "⚡ Générer"
#     st.rerun()

# APRÈS :
if st.button(
    "🎨 Ouvrir le Studio",
    type="primary",
    use_container_width=True,
    key=f"studio_{job['id']}",
):
    profile = load_profile()
    open_studio(job, profile)
```

### 4.2 — Déclencher depuis le Dashboard principal

Même remplacement dans la boucle `⭐ Offres à traiter` :

```python
# Dashboard.py — PAGE DASHBOARD — Bouton dans la boucle des offres

with action_cols[0]:
    if st.button(f"🎨 Studio", key=f"studio_dash_{j['id']}", use_container_width=True):
        profile = load_profile()
        open_studio(j, profile)
```

### 4.3 — Suppression d'offres dans la page Offres

Ajouter dans le `col_a` de la page `📋 Offres` :

```python
# Après le bouton "💾 Sauvegarder"
st.divider()
with st.expander("⚠️ Zone dangereuse"):
    if st.button(
        "🗑️ Supprimer cette offre",
        key=f"del_{job['id']}",
        use_container_width=True,
    ):
        db.delete_job(job["id"])
        st.warning("Offre supprimée.")
        st.rerun()
```

---

## Sprint 5 — Filtre date dans la page Scanner
**Durée estimée : 1h | Fichier : `Dashboard.py`**

```python
# Dashboard.py — PAGE SCANNER — Ajout filtre date (dans col2, après days slider)

show_date_filter = st.checkbox("Filtrer par date ajout", value=False)
if show_date_filter:
    date_from = st.date_input(
        "Offres ajoutées après le",
        value=date.today() - timedelta(days=30),
    )
    st.session_state["date_from_filter"] = date_from.isoformat()
else:
    st.session_state.pop("date_from_filter", None)

# Dans la page 📋 Offres, passer le filtre :
date_from = st.session_state.get("date_from_filter")
jobs = db.get_jobs(
    min_score=min_s,
    status=f_status if f_status != "Tous" else None,
    location_filter=f_city if f_city != "Toute la France" else None,
    search=search_q or None,
    date_from=date_from,   # ← NOUVEAU
    limit=300,
)
```

---

## Récapitulatif des fichiers modifiés

| Fichier | Type | Sprint | Lignes impactées |
|---|---|---|---|
| `engine/database.py` | Ajout méthodes | 0 | +30 lignes |
| `engine/database.py` | Modif `get_jobs()` | 0, 5 | +5 lignes |
| `engine/studio_analysis.py` | **NOUVEAU** | 1 | ~70 lignes |
| `Dashboard.py` | Nouveau dialog + helpers | 2, 3, 4 | +220 lignes |
| `Dashboard.py` | Filtres date + suppression | 0, 5 | +30 lignes |
| `engine/cv_generator.py` | Vérif injection override | 3 | ~5 lignes |

**Total : ~360 lignes de code nouvelles ou modifiées. Aucune table DB supprimée ou altérée.**

---

## Notes de déploiement Replit

- `engine/studio_analysis.py` : zéro import lourd (pas de numpy/matplotlib pour la heatmap — HTML pur).
- Le Copilote IA réutilise `PersonalCVGenerator().llm` déjà instancié : **aucun nouveau modèle chargé**.
- La heatmap HTML est générée côté serveur et passée à `st.components.v1.html()` : RAM minimale.
- La suppression de fichiers dans `delete_job()` est `missing_ok=True` : safe si les fichiers n'existent plus.
- Le `@st.dialog` Streamlit ≥ 1.35 est déjà utilisé dans ton stack → compatibilité garantie.

---

*Plan généré sur base de l'analyse de `Pipeline.py` (352 lignes) et `Dashboard.py` (1324 lignes) — repo `zeino-droid/cv`*
