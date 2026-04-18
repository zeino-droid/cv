# 🎯 Job Copilot — Objectif CDI France 2026

## 🚀 Commandes Sniper
- **Dashboard Premium :** `streamlit run Dashboard.py`
- **CLI Sniper (Postulage rapide) :** `python Sniper.py --min-score 60 --top 10`
- **Batch Pipeline :** `python Pipeline.py --top 20`

## 🏗 Architecture "Lean"
- **`engine/`** : Moteur de génération (1 seul appel LLM, ultra-rapide).
- **`profiles/`** : Données maîtres et profils thématiques (Simulation/Énergie).
- **`templates/`** : Design Typst (Le "Wow" factor).
- **`storage/`** : Persistance (SQLite `jobs.db`).
- **`vault/`** : Archivage des candidatures générées.

## ⚠️ Erreurs Interdites (Leçons Apprises)
1. **Sur-Ingénierie** : Ne pas recréer de complexité V7. Le code doit être une ligne droite vers le PDF.
2. **Multi-appels LLM** : Interdit. Tout doit tenir dans un seul prompt structuré (JSON).
3. **APIs Externes Lourdes** : Éviter. Sourcing via JobSpy uniquement.
4. **Hardcoded Paths** : Utiliser `Path` et vérifier l'existence avant d'agir.
5. **Désordre** : Ne jamais recréer les dossiers `config`, `data` ou `core`. Respecter la nouvelle structure.

## 💡 Règle d'Or
Un script qui n'aide pas à envoyer un CV qualifié **aujourd'hui** est inutile. Zein doit postuler, pas coder.

---
*Dernière mise à jour : Reorganisation Pro v3 — 18/04/2026*
