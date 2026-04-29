"""
✉️ LETTER RENDERER — Génération de lettres de motivation PDF via Typst.

Ce module fournit :
  - :class:`LetterRenderer` : compile un JSON structuré en PDF via le template
    ``templates/lettre_template.typ``.
  - :func:`build_letter_data` : construit le JSON structuré à partir du profil,
    du job et des paragraphes générés.
  - :func:`format_french_date` : formate une date en format français long.

Suit le même pattern que :class:`engine.rendering.TypstRenderer` pour la
compilation Typst (sys_inputs + JSON temporaire).
"""

from __future__ import annotations

import json
import locale
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import typst
except ImportError:
    typst = None

DEFAULT_TEMPLATE_PATH = Path("templates/lettre_template.typ")

# Mois français en dur pour éviter les soucis de locale sur serveur
_FRENCH_MONTHS = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril",
    5: "mai", 6: "juin", 7: "juillet", 8: "août",
    9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}

# Formules de politesse françaises classiques
FORMULES_POLITESSE = [
    "Je vous prie d'agréer, Madame, Monsieur, l'expression de mes salutations distinguées.",
    "Dans l'attente de votre retour, je vous prie d'agréer, Madame, Monsieur, mes sincères salutations.",
    "Je vous prie de croire, Madame, Monsieur, en l'expression de ma considération distinguée.",
]


def format_french_date(dt: Optional[datetime] = None) -> str:
    """Formate une date en format français long : '29 avril 2026'."""
    if dt is None:
        dt = datetime.now()
    return f"{dt.day} {_FRENCH_MONTHS[dt.month]} {dt.year}"


def build_letter_data(
    profile: Dict[str, Any],
    job: Dict[str, Any],
    paragraphs: List[str],
    *,
    closing_formula: Optional[str] = None,
    city: str = "Nancy",
) -> Dict[str, Any]:
    """Construit le JSON structuré attendu par ``lettre_template.typ``.

    Args:
        profile: Profil maître (master_profile.json).
        job: Dict de l'offre (title, company, location, …).
        paragraphs: Liste des paragraphes du corps de la lettre (4 idéalement).
        closing_formula: Formule de politesse. Si None, utilise la première par défaut.
        city: Ville de l'expéditeur pour la ligne « Ville, le date ».

    Returns:
        Dict prêt à être sérialisé en JSON pour le template Typst.
    """
    personal = profile.get("personal_info", {})
    name = personal.get("name", "Candidat")
    location = personal.get("location", "France")

    # Extraire la ville depuis la location du profil si possible
    if not city:
        # "France (mobilité nationale)" → "France"
        city = location.split("(")[0].strip() if location else "France"

    return {
        "sender": {
            "name": name,
            "email": personal.get("email", ""),
            "phone": personal.get("phone", ""),
            "location": location,
            "address": "",
        },
        "recipient": {
            "company": job.get("company", ""),
            "department": "Service des Ressources Humaines",
            "contact_name": "",
            "address": "",
        },
        "city": city,
        "date": format_french_date(),
        "subject": f"Candidature au poste de {job.get('title', 'ingénieur')}",
        "reference": job.get("reference", ""),
        "salutation": "Madame, Monsieur,",
        "paragraphs": paragraphs or [""],
        "closing_formula": closing_formula or FORMULES_POLITESSE[0],
        "signature_name": name,
    }


class LetterRenderer:
    """Génère des lettres de motivation PDF via le template Typst."""

    def __init__(self, template_path: Path = DEFAULT_TEMPLATE_PATH):
        self.template_path = template_path
        self.available = typst is not None

    def render(
        self,
        letter_data: Dict[str, Any],
        output_path: Path,
        *,
        theme: str = "premium",
    ) -> Optional[Path]:
        """Compile le JSON lettre en PDF via Typst.

        Args:
            letter_data: Données structurées de la lettre (cf. :func:`build_letter_data`).
            output_path: Chemin de sortie du PDF (extension forcée à .pdf).
            theme: Thème de couleur ('premium', 'subtle', 'ats').

        Returns:
            Path du PDF généré, ou None en cas d'erreur.
        """
        if not self.available:
            print("   ⚠️  Module 'typst' non installé — rendu PDF impossible.")
            return None

        if not self.template_path.exists():
            print(f"   ⚠️  Template introuvable : {self.template_path}")
            return None

        template_dir = self.template_path.resolve().parent
        data_path = template_dir / "_lettre_data.json"
        output_path = output_path.with_suffix(".pdf")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Écrire les données JSON temporaires
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(letter_data, f, ensure_ascii=False, indent=2)

        try:
            template_abs = str(self.template_path.resolve())
            pdf_abs = str(output_path.resolve())
            root_abs = str(template_dir.resolve())

            sys_inputs = {
                "data-path": "_lettre_data.json",
                "theme": theme,
            }

            typst.compile(
                template_abs,
                output=pdf_abs,
                root=root_abs,
                sys_inputs=sys_inputs,
            )
            return output_path

        except Exception as e:
            print(f"   ⚠️  Erreur Typst (lettre) : {e}")
            return None

        finally:
            data_path.unlink(missing_ok=True)

    def render_from_profile(
        self,
        profile: Dict[str, Any],
        job: Dict[str, Any],
        paragraphs: List[str],
        output_path: Path,
        *,
        theme: str = "premium",
        closing_formula: Optional[str] = None,
        city: str = "Nancy",
    ) -> Optional[Path]:
        """Raccourci : construit le JSON puis compile en PDF.

        Combine :func:`build_letter_data` + :meth:`render` en un seul appel.
        """
        letter_data = build_letter_data(
            profile, job, paragraphs,
            closing_formula=closing_formula,
            city=city,
        )
        return self.render(letter_data, output_path, theme=theme)


def save_letter_text_fallback(
    letter_text: str,
    output_path: Path,
) -> Path:
    """Sauvegarde la lettre en texte brut (.txt) — fallback si Typst échoue.

    Args:
        letter_text: Texte complet de la lettre.
        output_path: Chemin de sortie (.txt sera forcé).

    Returns:
        Path du fichier texte créé.
    """
    txt_path = output_path.with_suffix(".txt")
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    txt_path.write_text(letter_text, encoding="utf-8")
    return txt_path
