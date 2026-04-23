# 🎯 Job Copilot — Advanced Career Automation

Job Copilot is an AI-powered ecosystem designed for engineers to automate and optimize the job application process. It bridges the gap between job sourcing and high-quality document generation.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Gemini AI](https://img.shields.io/badge/AI-Gemini_Flash-blue?style=flat&logo=google-gemini)](https://ai.google.dev/)

## 🚀 Key Features

- **Smart AI Sourcing**: Automated job hunting via multi-source scrapers (Google Jobs, Glassdoor, ZipRecruiter) and dedicated APIs (Remotive).
- **Semantics & Ranking**: AI-driven re-ranking and semantic keyword expansion to find the most relevant opportunities.
- **V5 CV Engine**: Guarantees a **one-page PDF** output using the unique *Shrink-Loop* algorithm and *Fill-First* experience strategy.
- **STAR-K Framework**: Automatically structures professional experiences into the Situation-Task-Action-Result-KeySkills format.
- **Asynchronous Studio**: Real-time CV editing and live PDF preview with a background thread runner (pause/stop search functionality).

## 🛠 Tech Stack

- **Frontend**: Streamlit (Premium Dark Mode UI)
- **Engine**: Python, Asyncio, Threading
- **Intelligence**: Google Gemini Flash 1.5
- **Document Rendering**: Typst (Modern alternative to LaTeX)
- **Database**: SQLite (Local-first architecture)

## 📦 Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/zeino-droid/cv.git
   cd cv
   ```

2. **Set up Environment**:
   Create a `.env` file based on `.env.example` and add your API keys.

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Dashboard**:
   ```bash
   streamlit run Dashboard.py
   ```

## 🔒 Security & Privacy

This project follows strict privacy rules:
- **Local-first**: All personal profiles and job data stay on your local machine.
- **Secrets Management**: Sensitive keys are handled via `.env` and excluded from source control.

---
*Created by [Zein ELAJAMY](https://github.com/zeino-droid) — R&D Engineer candidate (ENSEM 2026)*
