from typing import Dict, List

class ProfileMatcher:
    """Matching intelligent profil maître ↔ offre d'emploi"""

    def __init__(self, master_profile: Dict):
        self.master = master_profile

    def match_skills(self, job: Dict) -> List[str]:
        """Identifie les compétences matchant l'offre"""
        skills_by_cat = self.master["skills"]
        required = set(s.lower() for s in job.get("required_skills", []))
        matching = []

        # Technical, Frameworks, Tools
        for cat in ["technical", "frameworks", "tools"]:
            for skill in skills_by_cat.get(cat, {}).keys():
                if any(skill.lower() in req or req in skill.lower() for req in required):
                    matching.append(skill)

        # Soft skills
        matching.extend(skills_by_cat.get("soft", [])[:2])
        return list(dict.fromkeys(matching))[:10]  # unique, max 10

    def select_achievements(self, job: Dict) -> List[Dict]:
        """Sélectionne et ordonne les réalisations par pertinence"""
        required_skills = set(s.lower() for s in job.get("required_skills", []))
        scored = []

        for exp in self.master.get("experiences", []):
            tech_used = " ".join(t.lower() for t in exp.get("technologies", []))
            for achievement in exp.get("achievements", []):
                score = 0
                ach_lower = achievement.lower()
                for skill in required_skills:
                    if skill in ach_lower or skill in tech_used: score += 2
                if any(c.isdigit() for c in achievement): score += 1
                for verb in self.master.get("writing_style", {}).get("preferred_verbs", []):
                    if verb.lower() in ach_lower: score += 0.5
                scored.append({"text": achievement, "score": score, "company": exp.get("company", ""), "position": exp.get("position", "")})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:8]

    def select_experiences(self, job: Dict) -> List[Dict]:
        """Sélectionne les expériences les plus pertinentes"""
        required_skills = set(s.lower() for s in job.get("required_skills", []))
        scored = []
        for exp in self.master.get("experiences", []):
            tech_used = [t.lower() for t in exp.get("technologies", [])]
            score = sum(1 for skill in required_skills if any(skill in t for t in tech_used))
            scored.append((score, exp))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored]

    def adapt_headline(self, job: Dict) -> str:
        """Adapte le headline au poste ciblé (heuristic)"""
        focus = job.get("focus", "")
        base_headline = self.master["headline"]
        headline_parts = [p.strip() for p in base_headline.split("|")]
        return headline_parts[0] if headline_parts else base_headline

    def select_projects(self, job: Dict) -> List[Dict]:
        """Sélectionne les projets pertinents"""
        required_skills = set(s.lower() for s in job.get("required_skills", []))
        scored = []
        for proj in self.master.get("projects", []):
            proj_tech = " ".join(t.lower() for t in proj.get("technologies", []))
            score = sum(1 for skill in required_skills if skill in proj_tech)
            scored.append((score, proj))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [proj for _, proj in scored[:2]]
