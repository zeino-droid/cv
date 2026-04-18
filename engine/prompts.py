from typing import Dict, List


class CVPromptBuilder:
    """Construit des prompts d'élite pour transformer un profil technique en candidat 'Incontournable'."""

    def __init__(self, master_profile: Dict, full_profile_md: str = ""):
        self.master = master_profile
        self.full_profile_md = full_profile_md

    def build_summary_prompt(self, job: Dict, matched_skills: List[str]) -> str:
        context_extra = (
            f"\nEXPÉRIENCES DÉTAILLÉES (Source d'impact):\n{self.full_profile_md[:2500]}"
            if self.full_profile_md
            else ""
        )
        skills = ", ".join(matched_skills[:8]) if matched_skills else "Expertise thermique/fluides/méca"
        
        return f"""Tu es un Chasseur de Têtes (Headhunter) spécialisé en ingénierie de pointe.
Ta mission : Vendre le profil de {self.master["identity"]["name"]} pour le poste de {job.get('title')} chez {job.get('company')}.

CANDIDAT:
- Nom: {self.master["identity"]["name"]}
- Statut Actuel: Ingénieur en 3ème et dernière année (Apprentissage) chez ArcelorMittal R&D.
- Expérience : Près de 3 ans d'expertise industrielle continue chez le leader mondial de l'acier.

PROFIL SOURCE:
{context_extra}

DIRECTIVES DE RÉDACTION (STYLE APPLE/CONSULTING):
1. INTERDICTION FORMELLE : Ne mentionne JAMAIS la date de disponibilité ou le statut d'étudiant/apprenti. On vend un EXPERT qui apporte de la valeur IMMEDIATEMENT.
2. TON : Autoritaire, technique, axé sur les résultats industriels. Pas de "passionné", "motivé" ou "je cherche".
3. IMPACT ET CONCISION (1 PAGE MAX): 
   - Résumé : 3 lignes maximum, ultra-dense.
   - Supprime tout verbiage. Va droit au but.
4. MOTS-CLÉS : Intègre chirurgicalement : {skills}.

RÉDIGE LE RÉSUMÉ (EN FRANÇAIS UNIQUEMENT):"""

    def build_headline_prompt(self, job: Dict) -> str:
        return f"""Génère un Titre de CV (Headline) puissant pour un poste de {job.get("title", "")}.

CONSIGNES STRICTES:
1. INTERDIT : "Jeune", "Apprenti", "Étudiant", "Septembre 2026", "Disponibilité".
2. STRUCTURE : Intitulé du Poste + Expertise Clé (ex: Ingénieur Simulation Numérique – FEA/CFD & Jumeaux Numériques).
3. TON : Doit sonner comme une personne avec 5 ans d'expérience.
4. LANGUE : Français uniquement.
5. LONGUEUR : Maximum 10 mots.

TITRE DU CV:"""

    def build_achievements_prompt(self, job: Dict, raw_achievements: List[Dict]) -> str:
        ach_text = "\n".join(
            f"- {a['text']} (Contexte: {a.get('company', 'R&D')})" for a in raw_achievements[:8]
        )
        return f"""Tu es un expert en optimisation de CV "Impact-First". 
Transforme ces réalisations brutes en accomplissements d'ingénieur senior.

RÉALISATIONS BRUTES:
{ach_text}

CONTEXTE DE L'OFFRE (Compétences cibles):
{", ".join(job.get("required_skills", []))}

RÈGLES D'OR:
1. FORMULE : [Verbe d'Action Fort] + [Projet Technique] + [RÉSULTAT CHIFFRÉ OU IMPACT BUSINESS].
2. CHIFFRES : Si un chiffre n'est pas présent, déduis l'impact logique (ex: fiabilisation, réduction de cycles, automatisation).
3. TECH : Précise l'outil (Abaqus, Metafor, Fluent, Python) comme un levier de performance, pas une fin en soi.
4. STYLE : Perforant, concis, technique (Impératif 1 page).
5. FORMAT : Exactement 3 puces d'impact commençant par "• ".

RÉDIGE LES 3 RÉALISATIONS (EN FRANÇAIS):"""

    def build_education_prompt(self, job: Dict, edu: Dict) -> str:
        return f"""Réécris cette formation pour qu'elle renforce la crédibilité technique pour le poste de {job.get("title")}.
Formation : {edu.get("degree")} à {edu.get("school")}.
Mission : 15 mots max. Focus sur la spécialisation la plus rare ou la plus valorisée pour le poste.
Français uniquement."""

    def build_review_prompt(self, job: Dict, cv_data: Dict) -> str:
        return f"""Analyse ce Headline et ce Summary. 
IMPACT ET CONCISION (IMPÉRATIF 1 PAGE):
   - Le CV DOIT tenir sur une seule page.
   - Supprime tout verbiage. Va droit au but.
   - Limite chaque expérience à 3-4 points d'impact maximum.
   - Chaque ligne doit rapporter du business ou de la performance technique.
   - Résumé : 3 lignes maximum, ultra-dense.
Supprime TOUT ce qui fait "junior", "scolaire" ou "disponible tard". 
Rends le tout "agressif" commercialement pour un recruteur technique.
Sortie au format JSON: {{"improved_headline": "...", "improved_summary": "..."}}"""

    def build_semantic_expansion_prompt(self, job: Dict) -> str:
        return f"""Identifie les 12 termes techniques les plus "chauds" et valorisables pour ce poste ({job.get('title')}).
Exemple : Jumeaux numériques, HPC, FEA non-linéaire, Couplage multi-physique.
Sépare par des virgules."""

    def build_fast_adaptation_prompt(self, job: Dict, matched_skills: List[str], cv_type: str) -> str:
        return self.build_summary_prompt(job, matched_skills) # Use the improved summary logic

