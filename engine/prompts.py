from typing import Dict, List


class CVPromptBuilder:
    """Construit des prompts courts, strictement en français, pour un CV naturel."""

    def __init__(self, master_profile: Dict, full_profile_md: str = ""):
        self.master = master_profile
        self.full_profile_md = full_profile_md

    def build_summary_prompt(self, job: Dict, matched_skills: List[str]) -> str:
        context_extra = (
            f"\nCONTEXTE COMPLET:\n{self.full_profile_md[:1500]}"
            if self.full_profile_md
            else ""
        )
        skills = (
            ", ".join(matched_skills[:8])
            if matched_skills
            else "compétences techniques"
        )
        return f"""Tu es un recruteur français expert en CV d'ingénieur.

CANDIDAT:
- Nom: {self.master["identity"]["name"]}
- Statut: {self.master.get("current_status", "")}
{context_extra}

OFFRE CIBLÉE:
- Adapte le résumé pour l'offre {job.get('title')} chez {job.get('company')}.
- IMPORTANT : Mentionner la disponibilité à partir de Septembre 2026.
- Met en avant les compétences : {skills}.
- Compétences attendues: {", ".join(job.get("required_skills", []))}

MISSION:
Rédige un résumé professionnel en français, naturel et fluide, en 3 phrases maximum.

CONSIGNES:
- Rédige uniquement en français.
- Ton clair, direct, humain et crédible.
- Mets en avant la valeur apportée.
- Intègre subtilement les mots-clés suivants: {skills}
- Ne cite pas le nom de l'entreprise cible.
- Évite les formules génériques comme "passionné par" ou "je recherche un stage".
- Ne fais pas de phrase trop longue.
- Évite tout ton robotique ou trop scolaire."""

    def build_headline_prompt(self, job: Dict) -> str:
        return f"""Rédige un titre de CV court, naturel et percutant pour le poste de {job.get("title", "")}.

CONSIGNES:
- Écris uniquement en français.
- Maximum 8 mots.
- Commence par "Ingénieur" ou "Jeune Ingénieur".
- IMPORTANT: Mentionner systématiquement la disponibilité à partir de Septembre 2026.
- Le titre doit sonner crédible pour un recruteur.
- Ne cite pas l'école, ni l'entreprise.
- Évite les titres trop lourds ou artificiels."""

    def build_achievements_prompt(self, job: Dict, raw_achievements: List[Dict]) -> str:
        ach_text = "\n".join(
            f"- {a['text']} (chez {a['company']})" for a in raw_achievements[:6]
        )
        return f"""Tu réécris des réalisations de CV pour un ingénieur en France.

OFFRE:
{", ".join(job.get("required_skills", [])[:5])}

RÉALISATIONS BRUTES:
{ach_text}

MISSION:
Réécris 4 réalisations en français naturel, fluide et attractif pour le recruteur.

CONSIGNES:
1. Commence par l'impact ou le résultat.
2. Utilise des verbes d'action forts.
3. Garde un style professionnel, simple et crédible.
4. Mentionne les outils techniques seulement s'ils apportent de la valeur.
5. Rédige exactement 4 puces.
6. Chaque puce doit commencer par "• ".
7. N'utilise aucun mot anglais inutile.
8. N'ajoute pas de commentaire, seulement les 4 puces."""

    def build_education_prompt(self, job: Dict, edu: Dict) -> str:
        return f"""Tu adapes une formation de CV pour un poste d'ingénieur.

POSTE:
{job.get("title")}

FORMATION:
{edu.get("degree")}
{edu.get("details", "")}

MISSION:
Réécris cette formation en français clair et naturel, en 15 mots maximum.

CONSIGNES:
- Mets en avant ce qui est pertinent pour le poste.
- Garde un ton crédible et professionnel.
- N'ajoute pas d'information inventée.
- Ne cite pas l'entreprise cible.
- Reste concis."""

    def build_review_prompt(self, job: Dict, cv_data: Dict) -> str:
        return f"""Tu es un relecteur de CV français.

POSTE CIBLÉ:
{job.get("title")}

CONTENU À RELIRE:
Headline: {cv_data.get("headline")}
Summary: {cv_data.get("summary")}

MISSION:
Corrige et améliore le texte pour qu'il soit plus naturel, plus fluide et plus convaincant pour un recruteur français.

CONSIGNES:
- Réponds uniquement en JSON.
- Garde le français.
- Améliore la fluidité.
- Supprime les formulations lourdes ou trop scolaires.
- Conserve le sens et les informations importantes.
- Ne rajoute pas d'informations inventées.

FORMAT DE SORTIE:
{{"improved_headline": "...", "improved_summary": "..."}}"""

    def build_semantic_expansion_prompt(self, job: Dict) -> str:
        return f"""Analyse ce poste et donne des mots-clés utiles pour un CV d'ingénieur.

POSTE:
{job.get("title")}
{job.get("description", "")[:400]}

MISSION:
Liste 12 mots-clés techniques ou métiers pertinents.

CONSIGNES:
- Réponds uniquement en français.
- Sépare les mots-clés par des virgules.
- Ne mets pas de phrase complète.
- Ne mélange pas avec de l'anglais inutile.
- Favorise les termes vraiment utiles pour un CV et un recruteur.
- Exemple de style: éléments finis, simulation numérique, thermomécanique, Python, CFD."""

    def build_fast_adaptation_prompt(self, job: Dict, matched_skills: List[str], cv_type: str) -> str:
        skills = ", ".join(matched_skills[:6])
        context = "Focus Simulation R&D, Abaqus, Metafor, calculs de structures" if cv_type == "simulation" else "Focus Énergie, Thermique, CFD, Ansys Fluent, Décarbonation"
        
        return f"""Tu es un expert en recrutement d'ingénieurs en France.
Adopte un ton très professionnel, naturel et crédible (évite le ton robotique).

OFFRE CIBLÉE:
- Poste: {job.get("title", "Ingénieur")}
- Entreprise: {job.get("company", "Confidentiel")}
- Profil cible retenu: {context}

CANDIDAT:
- Nom: {self.master["identity"]["name"]}
- Statut: {self.master.get("current_status", "")}

MISSION:
Adapte le titre (headline) et le résumé (summary) du CV pour ce poste précis.

CONSIGNES:
1. RÉSUMÉ (summary): 3 phrases maximum. Ton direct, focus sur la valeur ajoutée et les outils : {skills}. 
2. TITRE (headline): Court (max 8 mots), percutant, commençant par "Ingénieur".
3. Langue: FRANÇAIS uniquement.
4. Réponds UNIQUEMENT au format JSON.

FORMAT DE RÉPONSE:
{{
  "headline": "...",
  "summary": "..."
}}"""
