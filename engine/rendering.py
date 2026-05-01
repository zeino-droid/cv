import json
import re
import shutil
import subprocess
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pypdf import PdfReader

from config.theme import THEME

try:
    import typst
except ImportError:
    typst = None

DEFAULT_OUTPUT_DIR = Path("vault/resumes")
TYPST_TEMPLATE_PATH = Path("templates/cv_template.typ")


class Renderer:
    """Base class for CV renderers"""

    def render(self, cv_data: Dict, output_path: Path, **kwargs) -> Optional[Path]:
        raise NotImplementedError


class TypstRenderer(Renderer):
    """Génère des PDFs professionnels via Typst"""

    def __init__(self, template_path: Path = TYPST_TEMPLATE_PATH):
        self.template_path = template_path
        self.available = self._check_typst()

    def _check_typst(self) -> bool:
        return typst is not None

    def render(
        self,
        cv_data: Dict,
        output_path: Path,
        font_size_delta: float = 0.0,
        leading: float = 0.65,
        section_gap: float = 20.0,
        margin_sides: float = 14.0,
        photo_path: Optional[str] = None,
        theme: str = "premium",
        **kwargs,
    ) -> Optional[Path]:
        """
        Renders the CV using Typst.
        Supported kwargs:
            font_size_delta (float): Adjust font size globally.
            leading (float): Paragraph leading in em (default 0.65 for better readability).
            section_gap (float): Section spacing in pt (default 20.0 for clearer visual blocks).
            margin_sides (float): Right margin in pt.
            photo_path (str | None): Absolute path to the profile photo uploaded by the user.
                When provided the file is copied into the template directory so Typst can
                access it within its sandboxed root, then cleaned up after compilation.
            theme (str): Colour theme — "premium" (default), "subtle", or "ats".
        Defaults are aligned with the Typst template to avoid dense text rendering.
        """
        if not self.available or not self.template_path.exists():
            return None

        template_dir = self.template_path.resolve().parent
        data_path = template_dir / "_cv_data.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(cv_data, f, ensure_ascii=False, indent=2)

        # Resolve the photo: prefer the explicit path, fall back to legacy photo.jpg
        copied_photo: Optional[Path] = None
        resolved_photo_filename: Optional[str] = None

        if photo_path and Path(photo_path).is_file():
            source = Path(photo_path)
            suffix = source.suffix.lower() if source.suffix else ".jpg"
            dest_name = "_profile_photo" + suffix
            dest = template_dir / dest_name
            shutil.copy2(source, dest)
            copied_photo = dest
            resolved_photo_filename = dest_name
        elif (template_dir / "photo.jpg").exists():
            resolved_photo_filename = "photo.jpg"

        has_photo = resolved_photo_filename is not None

        try:
            if typst is None:
                raise ImportError("Le module python 'typst' n'est pas installé.")

            pdf_path = output_path.with_suffix(".pdf")

            # On passe tout en chemins absolus pour éviter les doutes
            template_abs = str(self.template_path.resolve())
            pdf_abs = str(pdf_path.resolve())
            root_abs = str(template_dir.resolve())

            sys_inputs = {
                "data-path": "_cv_data.json",
                "font-size-delta": f"{font_size_delta:.2f}",
                "leading": f"{leading:.2f}",
                "section-gap": f"{section_gap:.1f}",
                "margin-sides": f"{margin_sides:.1f}",
                "has-photo": "true" if has_photo else "false",
                "theme": theme,
                # Centralized theme colours from config/theme.py
                "sidebar-bg": THEME["sidebar_bg"],
                "accent-primary": THEME["accent_primary"],
                "sidebar-text": THEME["sidebar_text"],
                "sidebar-link": THEME["sidebar_link"],
                "sidebar-heading": THEME["sidebar_heading"],
                "sidebar-divider": THEME["sidebar_divider"],
                "body-text": THEME["body_text"],
                "meta-text": THEME["meta_text"],
            }
            if has_photo:
                sys_inputs["photo-path"] = resolved_photo_filename

            typst.compile(
                template_abs,
                output=pdf_abs,
                root=root_abs,
                sys_inputs=sys_inputs,
            )
            return pdf_path
        except Exception as e:
            # On tente de remonter l'erreur pour le debug dashboard
            cv_data["_last_error"] = str(e)
            print(f"   ⚠️  Erreur Typst: {e}")
        finally:
            data_path.unlink(missing_ok=True)
            if copied_photo is not None:
                copied_photo.unlink(missing_ok=True)
        return None

    def get_page_count(self, pdf_path: Path) -> int:
        """Détecte le nombre de pages du PDF généré."""
        try:
            # Utilise pdfinfo de poppler-utils si disponible
            result = subprocess.run(
                ["pdfinfo", str(pdf_path)], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if line.startswith("Pages:"):
                    return int(line.split(":")[1].strip())
        except Exception as e:
            print(f"   ⚠️ Erreur détection pages (pdfinfo): {e}")

        try:
            reader = PdfReader(str(pdf_path))
            return len(reader.pages)
        except Exception as e:
            print(f"   ⚠️ Erreur détection pages (pypdf): {e}")

        return 1


class MarkdownRenderer(Renderer):
    """Rend le CV en Markdown"""

    def render(self, cv_data: Dict, output_path: Path, **kwargs) -> Optional[Path]:
        identity = cv_data["identity"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        md = f"# {identity['name']}\n\n**{cv_data.get('headline', '')}**\n\n"

        # Contact Line
        contacts = [
            identity.get(k)
            for k in ["email", "phone", "location", "linkedin"]
            if identity.get(k)
        ]
        md += " | ".join(contacts) + "\n\n"

        # Summary
        md += f"## Résumé Professionnel\n\n{cv_data.get('summary', '')}\n\n"

        # Compétences
        md += "## Compétences Clés\n\n"
        grouped = cv_data.get("grouped_skills", {})
        for cat, skills in grouped.items():
            if skills:
                names = [s["name"] for s in skills]
                md += f"**{cat}:** {', '.join(names)}\n\n"

        # Expériences
        md += "## Expériences Professionnelles\n\n"
        for exp in cv_data.get("experiences", []):
            md += f"### {exp.get('position')} - **{exp.get('company')}**\n"
            md += f"*{exp.get('start_date', '')} – {exp.get('end_date', '')}* | {exp.get('location', '')}\n\n"
            for ach in exp.get("achievements", []):
                md += f"{ach if ach.startswith('•') else '• ' + ach}\n"
            md += "\n"

        # Formation
        md += "## Formation\n\n"
        for edu in cv_data.get("education", []):
            md += f"**{edu.get('degree')}** ({edu.get('year')}) - {edu.get('school')}\n"
            md += f"{edu.get('details', '')}\n\n"

        md_path = output_path.with_suffix(".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
        return md_path


class LatexRenderer(Renderer):
    """Rend le CV en LaTeX (ModernCV)"""

    def render(self, cv_data: Dict, output_path: Path, **kwargs) -> Optional[Path]:
        # Escape helper
        def esc(t):
            conv = {
                "&": r"\&",
                "%": r"\%",
                "$": r"\$",
                "#": r"\#",
                "_": r"\_",
                "{": r"\{",
                "}": r"\}",
            }
            return re.sub(
                "|".join(re.escape(k) for k in conv.keys()),
                lambda m: conv[m.group()],
                str(t),
            )

        identity = cv_data["identity"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        names = identity["name"].split()
        tex = r"\documentclass[11pt,a4paper,sans]{moderncv}" + "\n"
        tex += r"\moderncvstyle{classic}" + "\n\\moderncvcolor{blue}\n"
        tex += r"\usepackage[utf8]{inputenc}" + "\n"
        tex += f"\\firstname{{{esc(names[0])}}}\n"
        tex += f"\\familyname{{{esc(' '.join(names[1:]))}}}\n"
        tex += f"\\title{{{esc(cv_data.get('headline', ''))}}}\n"
        tex += f"\\phone{{{esc(identity.get('phone', ''))}}}\n"
        tex += f"\\email{{{esc(identity.get('email', ''))}}}\n\n"
        tex += "\\begin{document}\n\\makecvtitle\n\n"

        tex += f"\\section{{Résumé}}\n{esc(cv_data.get('summary', ''))}\n\n"

        tex += "\\section{Expériences}\n"
        for exp in cv_data.get("experiences", []):
            tex += f"\\cventry{{{esc(exp.get('start_date'))}}}{{{esc(exp.get('position'))}}}"
            tex += f"{{{esc(exp.get('company'))}}}{{{esc(exp.get('location'))}}}{{}}{{\n\\begin{{itemize}}\n"
            for ach in exp.get("achievements", []):
                tex += f"\\item {esc(ach.lstrip('•- ').strip())}\n"
            tex += "\\end{itemize}\n}\n"

        tex += "\n\\end{document}\n"

        tex_path = output_path.with_suffix(".tex")
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(tex)
        return tex_path
