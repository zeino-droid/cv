"""
engine/cv_generator.py
Studio Dynamique de Candidature — Moteur de génération CV + Lettre de motivation
Génère du Typst, compile en PDF via subprocess.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import google.generativeai as genai

# ---------------------------------------------------------------------------
# Configuration Gemini
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-1.5-flash"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_profile(profile_path: str = "master_profile.json") -> dict:
    with open(profile_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _gemini_call(prompt: str, system: str = "") -> str:
    """Appel simple à l'API Gemini."""
    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system if system else None,
    )
    response = model.generate_content(prompt)
    return response.text.strip()


# ---------------------------------------------------------------------------
# Prompts de génération
# ---------------------------------------------------------------------------

SYSTEM_CV = """Tu es un expert en rédaction de CV professionnels français (standards européens).
Tu génères du contenu CV authentique, chronologiquement cohérent, orienté métier.
Règles absolues :
- Respecte la chronologie réelle des expériences/études du candidat
- N'invente AUCUNE expérience ni compétence absente du profil
- Mets subtilement en avant les compétences pertinentes pour l'offre
- Accroche percutante (2 lignes max), résumé professionnel (4-5 lignes)
- Langage action (verbes d'action, chiffres si disponibles)
- Renvoie UNIQUEMENT du JSON structuré, aucun texte libre"""

SYSTEM_COVER = """Tu es un expert en lettres de motivation professionnelles françaises.
Tu rédiges des lettres authentiques, personnalisées, non génériques.
Règles absolues :
- Utilise uniquement les éléments réels du profil candidat
- Structure : accroche contextuelle → valeur ajoutée → motivation → call-to-action
- Ton professionnel mais humain, jamais robotique
- 3-4 paragraphes, 250-350 mots max
- Renvoie UNIQUEMENT le texte de la lettre (sans objet ni coordonnées)"""


def generate_cv_content(profile: dict, job_offer: dict) -> dict:
    """
    Génère le contenu structuré du CV via Gemini.
    Retourne un dict avec toutes les sections.
    """
    prompt = f"""Profil candidat :
{json.dumps(profile, ensure_ascii=False, indent=2)}

Offre d'emploi ciblée :
{json.dumps(job_offer, ensure_ascii=False, indent=2)}

Génère un CV complet en JSON avec cette structure EXACTE :
{{
  "accroche": "...",
  "resume_professionnel": "...",
  "experiences": [
    {{
      "poste": "...",
      "entreprise": "...",
      "periode": "...",
      "lieu": "...",
      "missions": ["...", "..."]
    }}
  ],
  "formations": [
    {{
      "diplome": "...",
      "etablissement": "...",
      "periode": "...",
      "mention": "..."
    }}
  ],
  "competences": {{
    "techniques": ["...", "..."],
    "outils": ["...", "..."],
    "langues": ["...", "..."],
    "soft_skills": ["...", "..."]
  }},
  "projets": [
    {{
      "nom": "...",
      "description": "...",
      "technologies": ["..."]
    }}
  ],
  "certifications": ["..."],
  "centres_interet": ["..."]
}}
Renvoie UNIQUEMENT le JSON, sans aucun texte avant ou après."""

    raw = _gemini_call(prompt, SYSTEM_CV)
    # Nettoyage des fences markdown éventuelles
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(raw)


def generate_cover_letter(profile: dict, job_offer: dict) -> str:
    """Génère le texte de la lettre de motivation."""
    prompt = f"""Profil candidat :
{json.dumps(profile, ensure_ascii=False, indent=2)}

Offre d'emploi :
{json.dumps(job_offer, ensure_ascii=False, indent=2)}

Rédige une lettre de motivation professionnelle, authentique, personnalisée.
Renvoie UNIQUEMENT le corps de la lettre (sans objet, sans coordonnées)."""

    return _gemini_call(prompt, SYSTEM_COVER)


# ---------------------------------------------------------------------------
# Assistant IA d'édition par section
# ---------------------------------------------------------------------------

SYSTEM_EDITOR = """Tu es un assistant expert en optimisation de CV et lettres de motivation.
L'utilisateur te donne une instruction précise pour modifier une section.
Tu as accès au profil complet du candidat pour rester factuel.
Règles :
- N'invente aucun fait absent du profil
- Applique exactement l'instruction donnée
- Renvoie UNIQUEMENT le contenu révisé de la section, même format que l'original
- Si la section est du JSON, renvoie du JSON. Si c'est du texte, renvoie du texte."""


def ai_edit_section(
    section_name: str,
    current_content: str,
    instruction: str,
    profile: dict,
    job_offer: dict,
) -> str:
    """
    Réécrit une section spécifique selon l'instruction utilisateur.
    Utilisé par le Studio d'édition.
    """
    prompt = f"""Section à modifier : {section_name}
Contenu actuel :
{current_content}

Instruction de l'utilisateur : {instruction}

Profil candidat complet (pour référence factuelle) :
{json.dumps(profile, ensure_ascii=False, indent=2)}

Contexte de l'offre :
{json.dumps(job_offer, ensure_ascii=False, indent=2)}

Renvoie uniquement le contenu révisé."""

    return _gemini_call(prompt, SYSTEM_EDITOR)


# ---------------------------------------------------------------------------
# Template Typst
# ---------------------------------------------------------------------------

TYPST_TEMPLATE = r"""
#set document(title: "{name} — CV")
#set page(
  paper: "a4",
  margin: (top: 1.8cm, bottom: 1.8cm, left: 2cm, right: 2cm),
)
#set text(font: "Linux Libertine", size: 10.5pt, lang: "fr")
#set par(justify: true, leading: 0.65em)

// Couleurs
#let accent = rgb("#1a3a5c")
#let lightgray = rgb("#f5f5f5")
#let midgray = rgb("#888888")

// Macro section
#let section(title) = [
  #v(0.5em)
  #line(length: 100%, stroke: 0.5pt + accent)
  #text(weight: "bold", size: 11pt, fill: accent)[#upper(title)]
  #v(0.2em)
]

// En-tête
#block(fill: accent, width: 100%, radius: 4pt, inset: 16pt)[
  #text(size: 22pt, weight: "bold", fill: white)[{name}]
  #h(1fr)
  #align(right)[
    #text(fill: white, size: 9.5pt)[
      {email} | {phone} | {location}
      #if "{linkedin}" != "" [ | {linkedin} ]
      #if "{github}" != "" [ | {github} ]
    ]
  ]
  #v(0.3em)
  #text(fill: rgb("#b0c4de"), size: 10.5pt, style: "italic")[{accroche}]
]

#v(0.4em)

// Résumé professionnel
#section("Résumé Professionnel")
#text(size: 10.5pt)[{resume}]

// Expériences professionnelles
#section("Expériences Professionnelles")
{experiences}

// Formations
#section("Formations")
{formations}

// Compétences
#section("Compétences")
#grid(
  columns: (1fr, 1fr),
  gutter: 1em,
  [
    *Techniques :* {competences_tech}
    
    *Outils :* {competences_outils}
  ],
  [
    *Langues :* {langues}
    
    *Soft skills :* {soft_skills}
  ]
)

// Projets
#if "{has_projets}" == "true" [
  #section("Projets & Réalisations")
  {projets}
]

// Certifications
#if "{has_certifs}" == "true" [
  #section("Certifications")
  {certifications}
]

// Centres d'intérêt
#if "{has_interets}" == "true" [
  #section("Centres d'Intérêt")
  #text(fill: midgray)[{interets}]
]
"""


def _build_experience_typst(exp: dict) -> str:
    missions = "\n".join(f"  - {m}" for m in exp.get("missions", []))
    return f"""#block(inset: (bottom: 0.5em))[
  #text(weight: "bold")[{exp.get('poste', '')}] #h(1fr) #text(fill: midgray)[{exp.get('periode', '')}]
  
  #text(style: "italic")[{exp.get('entreprise', '')}] — {exp.get('lieu', '')}
  
{missions}
]
"""


def _build_formation_typst(f: dict) -> str:
    mention = f" — {f['mention']}" if f.get("mention") else ""
    return f"""#block(inset: (bottom: 0.3em))[
  #text(weight: "bold")[{f.get('diplome', '')}]{mention} #h(1fr) #text(fill: midgray)[{f.get('periode', '')}]
  
  {f.get('etablissement', '')}
]
"""


def _build_projet_typst(p: dict) -> str:
    techs = ", ".join(p.get("technologies", []))
    return f"""#block(inset: (bottom: 0.3em))[
  *{p.get('nom', '')}* — {p.get('description', '')}
  
  #text(fill: midgray, size: 9.5pt)[{techs}]
]
"""


def cv_content_to_typst(cv: dict, profile: dict) -> str:
    """Convertit le dict CV en source Typst compilable."""
    contact = profile.get("contact", {})

    experiences_typst = "\n".join(
        _build_experience_typst(e) for e in cv.get("experiences", [])
    )
    formations_typst = "\n".join(
        _build_formation_typst(f) for f in cv.get("formations", [])
    )
    projets_typst = "\n".join(
        _build_projet_typst(p) for p in cv.get("projets", [])
    )

    comp = cv.get("competences", {})
    certifs = cv.get("certifications", [])
    interets = cv.get("centres_interet", [])

    source = TYPST_TEMPLATE.format(
        name=contact.get("nom", profile.get("nom", "Candidat")),
        email=contact.get("email", ""),
        phone=contact.get("telephone", ""),
        location=contact.get("localisation", ""),
        linkedin=contact.get("linkedin", ""),
        github=contact.get("github", ""),
        accroche=cv.get("accroche", ""),
        resume=cv.get("resume_professionnel", ""),
        experiences=experiences_typst,
        formations=formations_typst,
        competences_tech=", ".join(comp.get("techniques", [])),
        competences_outils=", ".join(comp.get("outils", [])),
        langues=", ".join(comp.get("langues", [])),
        soft_skills=", ".join(comp.get("soft_skills", [])),
        has_projets="true" if cv.get("projets") else "false",
        projets=projets_typst,
        has_certifs="true" if certifs else "false",
        certifications=", ".join(certifs),
        has_interets="true" if interets else "false",
        interets=", ".join(interets),
    )
    return source


# ---------------------------------------------------------------------------
# Template Typst pour la Lettre de Motivation
# ---------------------------------------------------------------------------

COVER_TEMPLATE = r"""
#set document(title: "Lettre de Motivation")
#set page(paper: "a4", margin: (top: 2cm, bottom: 2cm, left: 2.5cm, right: 2.5cm))
#set text(font: "Linux Libertine", size: 11pt, lang: "fr")
#set par(justify: true, leading: 0.75em)

#let accent = rgb("#1a3a5c")

// En-tête expéditeur
#text(size: 13pt, weight: "bold", fill: accent)[{name}]

{email} | {phone} | {location}

#v(1em)
#line(length: 100%, stroke: 0.5pt + accent)
#v(0.5em)

// Destinataire & Date
#align(right)[
  {city}, le {date}
  
  *{company}*
  
  {job_title}
]

#v(1.5em)

// Objet
*Objet : Candidature au poste de {job_title}*

#v(1em)

// Corps de la lettre
{body}

#v(2em)

Cordialement,

#text(weight: "bold")[{name}]
"""


def cover_letter_to_typst(letter_body: str, profile: dict, job_offer: dict) -> str:
    """Convertit la lettre en source Typst compilable."""
    import datetime

    contact = profile.get("contact", {})
    today = datetime.date.today().strftime("%d/%m/%Y")

    # Échapper les caractères spéciaux Typst dans le corps
    body_escaped = letter_body.replace("#", r"\#").replace("@", r"\@")

    return COVER_TEMPLATE.format(
        name=contact.get("nom", profile.get("nom", "Candidat")),
        email=contact.get("email", ""),
        phone=contact.get("telephone", ""),
        location=contact.get("localisation", ""),
        city=contact.get("ville", contact.get("localisation", "Paris")),
        date=today,
        company=job_offer.get("entreprise", job_offer.get("company", "Entreprise")),
        job_title=job_offer.get("titre", job_offer.get("title", "Poste")),
        body=body_escaped,
    )


# ---------------------------------------------------------------------------
# Compilation Typst → PDF
# ---------------------------------------------------------------------------

def compile_typst_to_pdf(typst_source: str, output_path: str) -> bool:
    """
    Compile une source Typst en PDF.
    Nécessite que `typst` soit installé dans le PATH.
    Retourne True si succès, False sinon.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".typ", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(typst_source)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["typst", "compile", tmp_path, output_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"[Typst Error] {result.stderr}")
            return False
        return True
    except FileNotFoundError:
        print("[Typst] Typst n'est pas installé. Tentative de fallback HTML→PDF.")
        return _fallback_html_to_pdf(typst_source, output_path)
    except subprocess.TimeoutExpired:
        print("[Typst] Timeout lors de la compilation.")
        return False
    finally:
        os.unlink(tmp_path)


def _fallback_html_to_pdf(typst_source: str, output_path: str) -> bool:
    """
    Fallback si Typst n'est pas installé :
    génère un PDF via WeasyPrint depuis un HTML formaté.
    """
    try:
        from weasyprint import HTML

        # Extraction basique du contenu depuis le source Typst (mode dégradé)
        html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 800px; margin: 40px auto; color: #222; }}
  pre {{ white-space: pre-wrap; font-family: inherit; }}
</style>
</head>
<body><pre>{typst_source}</pre></body>
</html>"""
        HTML(string=html_content).write_pdf(output_path)
        return True
    except ImportError:
        print("[Fallback] WeasyPrint non disponible.")
        return False


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def generate_full_application(
    profile_path: str,
    job_offer: dict,
    output_dir: str = "output",
    job_id: Optional[str] = None,
) -> dict:
    """
    Pipeline complet : profil + offre → CV PDF + Lettre PDF.
    Retourne un dict avec les chemins et le contenu intermédiaire.
    """
    os.makedirs(output_dir, exist_ok=True)
    profile = _load_profile(profile_path)

    prefix = job_id or "application"
    cv_json_path = os.path.join(output_dir, f"{prefix}_cv.json")
    cv_pdf_path = os.path.join(output_dir, f"{prefix}_cv.pdf")
    letter_txt_path = os.path.join(output_dir, f"{prefix}_letter.txt")
    letter_pdf_path = os.path.join(output_dir, f"{prefix}_letter.pdf")

    # 1. Générer le contenu CV
    cv_content = generate_cv_content(profile, job_offer)
    with open(cv_json_path, "w", encoding="utf-8") as f:
        json.dump(cv_content, f, ensure_ascii=False, indent=2)

    # 2. Générer la lettre
    letter_text = generate_cover_letter(profile, job_offer)
    with open(letter_txt_path, "w", encoding="utf-8") as f:
        f.write(letter_text)

    # 3. Compiler en PDF
    cv_typst = cv_content_to_typst(cv_content, profile)
    cv_pdf_ok = compile_typst_to_pdf(cv_typst, cv_pdf_path)

    letter_typst = cover_letter_to_typst(letter_text, profile, job_offer)
    letter_pdf_ok = compile_typst_to_pdf(letter_typst, letter_pdf_path)

    return {
        "profile": profile,
        "cv_content": cv_content,
        "cv_typst": cv_typst,
        "cv_pdf_path": cv_pdf_path if cv_pdf_ok else None,
        "letter_text": letter_text,
        "letter_typst": letter_typst,
        "letter_pdf_path": letter_pdf_path if letter_pdf_ok else None,
        "job_offer": job_offer,
    }
