# Smart AI Resume Analyzer - BCA 3rd Year Project (2026)

**ATS Resume Scanner for Campus Placements** — Flask + SQLite + NLP (TF-IDF) — No API key, runs offline.

### 🎯 Problem
70% of resumes are rejected by ATS before reaching HR. Students don't know *why*. This project gives an instant score (0-100) + exactly what to fix.

### ✨ Features (for viva - easy to explain)
1. **Auth** - Register/Login (SQLite), Admin panel
2. **Parser** - PDF/DOCX/TXT → text (PyPDF2/python-docx)
3. **Scoring Engine**:
   - Keyword Match (JD frequency weighted) - 40%
   - TF-IDF Cosine Semantic - 30%
   - Skill Coverage (70+ skills DB) - 20%
   - ATS Structure (sections, email, bullets) - 10%
4. **Dashboard** - History, Avg score, Recent analyses
5. **Result Page** - Verdict, Skills Gap, Missing Keywords, Fixes
6. **API**: `POST /api/analyze` → JSON

### 🛠️ Tech Stack
- Backend: Python 3, Flask
- DB: SQLite (`database/app.db`)
- NLP: scikit-learn TfidfVectorizer + fallback Jaccard
- Frontend: HTML/CSS (no React needed - viva friendly)

### 📁 Structure
```
BCA_Resume_Analyzer/
  app.py              # Flask app (login, dashboard, analyze)
  analyser.py         # Core logic (scoring, ATS checks) - explain 1-by-1 in viva
  web_stdlib.py       # Zero-dep HTTP server alternative
  requirements.txt
  templates/          # index, login, dashboard, analyze, result
  static/style.css
  database/app.db     # auto-created
  uploads/
  sample_data/
  docs/               # Synopsis, SRS, Report (see below)
```

### 🚀 How to Run (College PC / Termux)
```bash
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
# login: admin / admin123   or Register
```
*No deps?* `python web_stdlib.py` → http://127.0.0.1:8000

### 📊 Demo Data
In `analyser.py`: DEMO_CV + DEMO_JD (already filled in forms)
CLI: `python analyser.py --demo`

### 📄 Documentation for Submission
- `SYNOPSIS.md` - 1-page synopsis (copy to Word)
- `PROJECT_REPORT.md` - Full report outline (Abstract, Objectives, DFD, ER, Modules)
- `PPT_OUTLINE.md` - 12 slides
- `VIVA_QUESTIONS.md` - 50 Q&A
- `database/schema.sql`

### 🔑 Viva Tips
- Explain formula: `Overall = 0.4*keyword + 0.3*semantic + 0.2*skill + 0.1*ATS`
- ATS checks: email, sections, bullets, action verbs, length
- Why TF-IDF? Lightweight, no LLM cost, explainable
- Future: Add BERT embeddings, JD auto-fetch from LinkedIn

### 👨‍🎓 Submitted by
BCA 3rd Year - [Your Name] - [Roll No] - [College Name] 2026
Guide: [Guide Name]
