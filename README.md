# 📄 Resume_Analyzer — Smart AI Resume Analyzer (Dark Neon)

<p align="center">
  <img src="https://img.shields.io/badge/BCA-3rd_Year-6366f1?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.11-06b6d4?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/Flask-3.1黑-000000?style=for-the-badge&logo=flask" />
  <img src="https://img.shields.io/badge/Live-Demo-10b981?style=for-the-badge" />
  <a href="https://github.com/amanverma-bot/Resume_Analyzer"><img src="https://img.shields.io/github/stars/amanverma-bot/Resume_Analyzer?style=for-the-badge" /></a>
</p>

<p align="center">
  <b>ATS Resume Scanner for Campus Placements</b> — <b>Dark Neon Glass UI</b> • Flask + SQLite + NLP (TF-IDF/BERT) • No API key, offline
  <br/>
  <a href="https://switching-parts-bryan-murray.trycloudflare.com"><b>🌐 Live Demo</b></a> • <a href="#-features">Features</a> • <a href="#-quick-start">Quick Start</a> • <a href="#-viva">Viva</a>
</p>

> **70% resumes rejected by ATS before HR sees them.** This gives instant **ATS score 0-100** + exactly what to fix — like Jobscan, but free & offline for BCA.

---

### ✨ Features (viva-easy, explain 1-by-1)

| # | Feature | What it does | Viva line |
|---|---------|--------------|-----------|
| 1 | **🔐 Auth** | Register/Login (SQLite), Admin `admin/admin123` | `app.py:login_required` |
| 2 | **📄 Parser** | PDF/DOCX/TXT → text (PyPDF2) | `analyser.py:read_pdf` |
| 3 | **🎯 Scoring** | 40% Keyword (freq-weighted) + 30% Semantic (TF-IDF/BERT) + 20% Skills (70+ DB) + 10% ATS | `overall_score()` |
| 4 | **📊 Dashboard** | History, Avg score, donut + bars | `templates/result.html` |
| 5 | **🤖 AI Enhance** | Rewrites bullets STAR + metrics, injects missing | `ai_enhance_cv()` |
| 6 | **✨ AI Builder** | Create CV from form → ATS-safe | `ai_build_cv()` |
| 7 | **✉️ Cover Letter** | Tailored letter to JD | `ai_cover_letter()` |
| 8 | **🎤 Mock Interview** | 7 Qs + 0-10 feedback (STAR) | `generate_mock_questions()` |
| 9 | **🔗 JD Import** | Paste LinkedIn URL → auto-fetch | `fetch_jd_from_url()` |
| 10 | **📄 PDF Export** | Report + Enhanced CV (ReportLab) | `/download/report/<id>` |
| 11 | **🌙 Dark Neon UI** | Glass, glow, typing animation, toggle | `static/style.css` |

**APIs:** `POST /api/analyze`, `/api/enhance`, `/api/cover-letter`, `/api/mock-interview` → JSON

---

### 🛠️ Tech Stack

- **Backend:** Python 3.11, Flask 3.1, SQLite (`database/app.db`)
- **NLP:** scikit-learn TF-IDF + optional `sentence-transformers` BERT (`all-MiniLM-L6-v2`, fallback Jaccard)
- **Parsing:** PyPDF2, python-docx
- **PDF:** ReportLab
- **Frontend:** Jinja2 + Inter + CSS glass/neon (no React — viva friendly)
- **Deploy:** Docker, Render, Cloudflare Quick Tunnel (`cloudflared`), `localhost.run`

---

### 📁 Structure

```
Resume_Analyzer/
  app.py              # Flask (auth, dashboard, analyze, builder, cover, mock)
  analyser.py         # Core: scoring, ATS, AI builders — explain line-by-line
  templates/          # index (neon hero), analyze, result (donut), enhance, builder, cover, mock
  static/style.css    # Dark neon glass theme
  database/schema.sql
  requirements.txt
  SYNOPSIS.md / PROJECT_REPORT.md / PPT_OUTLINE.md / VIVA_QUESTIONS.md
  sample_data/
```

---

### 🚀 Quick Start (College PC / Termux)

```bash
git clone https://github.com/amanverma-bot/Resume_Analyzer.git
cd Resume_Analyzer
pip install -r requirements.txt  # flask PyPDF2 python-docx scikit-learn reportlab
python app.py
# open http://127.0.0.1:5000
# login: admin / admin123  or Register
```
No deps? `python web_stdlib.py` → http://127.0.0.1:8000

**Public tunnel (Termux):**
```bash
# Cloudflare Quick Tunnel (needs: pkg install cloudflared proot)
# proot fixes DNS: Go resolver reads /etc/resolv.conf which is read-only on Android
nohup proot -b $PREFIX/etc/resolv.conf:/etc/resolv.conf cloudflared tunnel \
  --protocol http2 --url http://localhost:5000 --no-autoupdate > tunnel_cf.log 2>&1 &
cat tunnel_cf.log | grep trycloudflare
```

---

### 📊 Demo

- **Demo CV/JD:** in `analyser.py:DEMO_CV` (pre-filled in forms)
- **CLI:** `python analyser.py --demo` → pretty report
- **Live:** https://switching-parts-bryan-murray.trycloudflare.com

---

### 📄 Submission Ready

- `SYNOPSIS.md` — 1-page synopsis
- `PROJECT_REPORT.md` — 13 chapters (Abstract, DFD, ER)
- `PPT_OUTLINE.md` — 12 slides
- `VIVA_QUESTIONS.md` — 50 Q&A
- `database/schema.sql` — ER

---

### 🔑 Viva Tips

- Formula: `Overall = 0.4*keyword + 0.3*semantic + 0.2*skill + 0.1*ATS`
- ATS: email, sections, bullets, verbs, length, metrics
- Why TF-IDF? Light, explainable, offline. BERT optional: `pip install sentence-transformers torch`
- Show code: `analyser.py:289` (BERT), `app.py:264` (PDF)

---

### 👨‍🎓 Submitted by

**BCA 3rd Year — [Your Name] — [Roll No] — [College Name] 2026**  
Guide: [Guide Name]  
GitHub: [@amanverma-bot/Resume_Analyzer](https://github.com/amanverma-bot/Resume_Analyzer) • Live: https://switching-parts-bryan-murray.trycloudflare.com

<p align="center">Made with ❤️ for placements — Dark Neon Edition 🌙</p>
