# 🚀 IDE Setup Guide - CV + Job Tracker Project

Ce guide te permet de configurer complètement ton IDE (VSCode) pour développer sur ce projet monorepo.

## 📋 Table des Matières

1. [Prérequis](#prérequis)
2. [Installation Automatique](#installation-automatique)
3. [Extensions VSCode](#extensions-vscode)
4. [Configuration des Outils](#configuration-des-outils)
5. [Vérification de l'Installation](#vérification-de-linstallation)
6. [Commandes Utiles](#commandes-utiles)
7. [Troubleshooting](#troubleshooting)

---

## 🔧 Prérequis

Avant de commencer, assure-toi que tu as installé :

### Système d'exploitation
- **macOS** (Apple Silicon M1+ recommandé) ou Linux/Windows avec WSL2

### Logiciels Obligatoires

```bash
# Python 3.9+
python3 --version

# Node.js 18+ et npm
node --version
npm --version

# Git
git --version

# Homebrew (pour macOS)
brew --version
```

### Installation via Homebrew (macOS)

```bash
# Python
brew install python@3.11

# Node.js
brew install node

# Git
brew install git

# Outils supplémentaires recommandés
brew install ollama       # Pour LLM local
brew install typst        # Pour rendu PDF
brew install docker       # Pour le full-stack
```

---

## ⚡ Installation Automatique

### Étape 1: Cloner le Repo

```bash
git clone <your-repo-url>
cd cv
```

### Étape 2: Exécuter le Script de Setup

```bash
bash setup.sh
```

Ce script va automatiquement :
- ✅ Vérifier Python 3.8+
- ✅ Créer un virtual environment `.venv`
- ✅ Installer les dépendances Python
- ✅ Configurer les variables d'environnement

### Étape 3: Ouvrir dans VSCode

```bash
code .
```

VSCode te demandera d'installer les extensions recommandées. **Accepte tout !**

---

## 🔌 Extensions VSCode

Ces extensions sont recommandées et pré-configurées. Tu peux les installer automatiquement via `.vscode/extensions.json` ou manuellement.

### Installation Rapide de Toutes les Extensions

```bash
# Copie-colle ces commandes dans le terminal VSCode (Ctrl+` ou Cmd+`)
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-python.black-formatter
code --install-extension charliermarsh.ruff
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension eamodio.gitlens
code --install-extension github.copilot
code --install-extension ms-vscode-remote.remote-containers
code --install-extension ms-azuretools.vscode-docker
```

### 🐍 Python Development

| Extension | ID | Rôle |
|-----------|--------|------|
| **Python** | `ms-python.python` | Support complet Python + debugging |
| **Pylance** | `ms-python.vscode-pylance` | IntelliSense avancé (Pylance) |
| **Black Formatter** | `ms-python.black-formatter` | Formatage de code Python |
| **Ruff** | `charliermarsh.ruff` | Linting ultra-rapide |
| **Debugpy** | `ms-python.debugpy` | Debugging Python |

### 📝 JavaScript/TypeScript

| Extension | ID | Rôle |
|-----------|--------|------|
| **ESLint** | `dbaeumer.vscode-eslint` | Linting JavaScript/TypeScript |
| **Prettier** | `esbenp.prettier-vscode` | Formatage code (JS/TS/JSON) |
| **Vue/TypeScript** | `typescript-vue.vue` | Support Vue 3 |
| **Tailwind CSS** | `bradlc.vscode-tailwindcss` | Autocomplétion Tailwind |

### 🔧 DevOps & Tools

| Extension | ID | Rôle |
|-----------|--------|------|
| **GitLens** | `eamodio.gitlens` | Annnotations Git avancées |
| **Docker** | `ms-azuretools.vscode-docker` | Support Docker |
| **Remote Containers** | `ms-vscode-remote.remote-containers` | Dev dans conteneurs |
| **Remote SSH** | `ms-vscode-remote.remote-ssh` | Dev sur serveurs distants |

### 🤖 AI & Productivity

| Extension | ID | Rôle |
|-----------|--------|------|
| **GitHub Copilot** | `github.copilot` | Autocomplétion IA |
| **Copilot Chat** | `github.copilot-chat` | Chat IA dans VSCode |
| **Todo Tree** | `gruntfuggly.todo-tree` | Gestion des TODOs |

---

## ⚙️ Configuration des Outils

### 1. Python Virtual Environment

VSCode doit automatiquement détecter le `.venv`. Sinon, force-le :

```bash
# Dans VSCode, ouvre la Command Palette (Cmd+Shift+P)
# et cherche "Python: Select Interpreter"
# Choisis: ./cv/.venv/bin/python
```

### 2. Formatters & Linters

Les configurations sont déjà dans `.vscode/settings.json` :

**Black** (formateur Python) :
```bash
pip install black==24.1.1
```

**Ruff** (linter Python) :
```bash
pip install ruff==0.5.0
```

**Prettier** (formateur Web) :
```bash
cd apps/web
npm install prettier --save-dev
```

### 3. Type Checking

**Pylance** (inclus avec l'extension Python) fait le type checking automatiquement.

Pour Python 3.10+, ajoute simplement les type hints :

```python
from typing import Optional, List

def process_data(items: List[str]) -> Optional[dict]:
    return None
```

### 4. Testing Framework

**Pytest** est déjà installé. Configure-le :

```bash
# Exécute les tests
pytest tests/ -v

# Ou via VSCode (Test Explorer)
# Cmd+Shift+P → "Test: Run All Tests"
```

---

## ✅ Vérification de l'Installation

### Checklist Finale

```bash
# 1. Vérifie Python
python3 -m pip --version

# 2. Vérifie que le venv est actif
which python
# Doit afficher: /Users/zeinelajamy/cv/.venv/bin/python

# 3. Installe les dépendances
pip install -r requirements.txt

# 4. Teste les imports
python3 -c "import fastapi; import pandas; import pydantic; print('✅ All imports OK')"

# 5. Vérifie Node.js
node --version && npm --version

# 6. Teste le build web
cd apps/web && npm install && npm run build

# 7. Vérifie Typst (optionnel)
typst --version
```

### Résultat Attendu

```
✅ Python 3.11.x
✅ Node.js 18+
✅ npm 9+
✅ All imports OK
✅ Typst 0.x
```

---

## 🎯 Commandes Utiles

### Backend Python

```bash
# Démarrer l'API FastAPI
python main.py

# Ou via le script
bash scripts/dev/api.sh

# Lancer les tests
pytest tests/ -v -s

# Formater le code
black .

# Linter
ruff check .
```

### Frontend Web

```bash
# Aller dans le dossier web
cd apps/web

# Installer les dépendances
npm install

# Démarrer le serveur Vite
npm run dev

# Build pour production
npm run build
```

### Full Stack Docker

```bash
# Démarrer tout le stack
bash scripts/dev/fullstack.sh

# Arrêter
make fullstack-down
```

### Makefile Shortcuts

```bash
# API dev
make api-dev

# Web dev
make web-dev

# Full stack
make fullstack-up
make fullstack-down

# Build web
make web-build
```

---

## 🐛 Troubleshooting

### Problem: "Python interpreter not found"

**Solution:**
```bash
# 1. Vérifie que Python est installé
python3 --version

# 2. Force VSCode à utiliser le bon interpréteur
# Cmd+Shift+P → "Python: Select Interpreter"
# Choisis: /Users/zeinelajamy/cv/.venv/bin/python
```

### Problem: "Module not found: fastapi, pandas, etc."

**Solution:**
```bash
# Assure-toi que le venv est activé
source .venv/bin/activate

# Réinstalle les dépendances
pip install -r requirements.txt --upgrade
```

### Problem: "npm command not found"

**Solution:**
```bash
# Install Node.js via Homebrew
brew install node

# Ou télécharge depuis https://nodejs.org/
```

### Problem: "npm: ERR! code ERESOLVE"

**Solution:**
```bash
cd apps/web
npm install --legacy-peer-deps
```

### Problem: "Port 5173 already in use" (Vite)

**Solution:**
```bash
# Trouve le process qui occupe le port
lsof -i :5173

# Tue le process
kill -9 <PID>

# Ou choisis un autre port
npm run dev -- --port 3000
```

### Problem: "Docker daemon not running"

**Solution:**
```bash
# Sur macOS, démarre Docker Desktop
open /Applications/Docker.app

# Ou si installé via Homebrew
brew services start docker
```

### Problem: Pylance IntelliSense ne fonctionne pas

**Solution:**
```bash
# 1. Redémarre VSCode (Cmd+Shift+P → "Developer: Reload Window")
# 2. Ou désactive/réactive l'extension Pylance
# 3. Assure-toi que Python est correctement sélectionné
```

---

## 📚 Ressources Additionnelles

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **React Docs**: https://react.dev/
- **Vite Guide**: https://vitejs.dev/
- **Python Testing (Pytest)**: https://docs.pytest.org/
- **Pydantic**: https://docs.pydantic.dev/
- **Pandas**: https://pandas.pydata.org/

---

## 🎨 Keyboard Shortcuts (VSCode)

| Action | Shortcut |
|--------|----------|
| Command Palette | `Cmd+Shift+P` |
| Format Document | `Cmd+Shift+I` |
| Start Debugging | `F5` |
| Open Terminal | `Ctrl+`` |
| Multi-cursor | `Cmd+D` (repeat) |
| Go to Definition | `Cmd+Click` |
| Find & Replace | `Cmd+H` |
| Git: Commit | `Ctrl+Shift+G` |

---

## ✨ Pro Tips

1. **Use the Test Explorer**: VSCode intègre Pytest. Clique sur l'icône "Test" dans la sidebar pour exécuter les tests avec un GUI.

2. **Debug Mode**: Appuie sur F5 pour lancer le debugger. Les breakpoints fonctionnent parfaitement avec l'extension Python.

3. **Format on Save**: Tu as déjà `formatOnSave: true` dans les settings. Tu peux aussi faire `Cmd+Shift+I` manuellement.

4. **Git Blame with GitLens**: Hover sur une ligne pour voir l'historique Git. C'est ultra utile.

5. **Pylance Type Hints**: Ajoute des type hints pour avoir une meilleure autocomplétion et détection d'erreurs.

6. **Run Entire Vite Stack**: Dans Terminal → Run Task → "Node: Web Dev Server" pour lancer Vite avec live-reload.

---

## 📝 Notes pour Ton Setup Spécifique

- **Apple Silicon (M1+)**: Les packages comme PyTorch sont auto-optimisés. Aucun problème attendu.
- **Ollama**: Si tu veux du LLM local, `ollama pull mistral:7b-instruct-v0.3-q4_K_M` est pré-configuré.
- **Typst**: Pour les PDF, `brew install typst` rend les CVs en ~30ms.

---

**Dernière mise à jour**: 2025
**Testé sur**: macOS 13+, Apple Silicon M1+, VSCode 1.95+