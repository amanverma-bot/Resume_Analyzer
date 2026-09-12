# PROJECT REPORT - Smart AI Resume Analyzer (Full Outline - Copy to Word/PDF)

**College:** [Your College Name]
**Dept:** Bachelor of Computer Applications
**Project:** Smart AI Resume Analyzer (ATS Scanner for Campus Placements)
**Submitted by:** [Name] - [Roll] - BCA 3rd Year 6th Sem 2026
**Guide:** [Guide Name]

---
### Certificate + Acknowledgement + Abstract (copy template from college)
**Abstract:** This project implements an ATS-inspired resume analyzer using Python NLP. It parses PDF/DOCX resumes, compares against JD using keyword, semantic (TF-IDF), skill coverage, and structure checks, producing an explainable 0-100 score with gaps and fixes. Flask web app with SQLite history helps students iteratively improve resumes before placements. No cloud API needed, runs offline.

### 1. Introduction
1.1 ATS problem - 75% rejection stats
1.2 Need for feedback tool in colleges
1.3 Proposed solution overview

### 2. Literature Survey
2.1 Existing: Jobscan, SkillSyncer (paid, black-box)
2.2 Gap: No offline, no explainable scoring for students
2.3 TF-IDF vs BERT tradeoffs (chosen TF-IDF for viva simplicity)

### 3. Objectives
- Instant ATS-like scoring
- Skill gap detection
- Keyword actionable fixes
- History tracking

### 4. System Analysis
4.1 Feasibility (Technical: Python available, Economical: free, Operational: browser only)
4.2 Requirements (as in SYNOPSIS)

### 5. System Design
5.1 **Architecture Diagram:**
```
[Browser] ↔ Flask (Routes: /, /login, /analyze, /api) ↔ analyser.py ↔ SQLite
                ↑ uses PyPDF2/docx → text
```
5.2 **DFD Level 0:** User → System (Upload Resume + JD) → Score Report
5.2 **DFD Level 1:** Auth, Parser, Extractor, Scorer, DB, Renderer
5.3 **ER Diagram:**
```
Users(id, username, password, email)
  1 ──* Analyses(id, user_id, overall, verdict, scores, skills json, result json, date)
```
5.4 **Use Case:** Student: Register, Login, Upload, View history. Admin: View all.

### 6. Modules Detail
(Explain each - 1 para + flowchart)
- Auth: session dict
- Parser: load_file() per extension
- Skill Extractor: SKILLS_DB 70 entries regex
- Scoring: keyword_match_score(), semantic_similarity()
- ATS: ats_checks() - 8 rules

### 7. Technology
- Python, Flask, SQLite, PyPDF2, python-docx, scikit-learn
- Frontend: Jinja2 + CSS

### 8. Implementation
- `analyser.py:137-151` skill extraction snippet
- `analyser.py:233-261` keyword scoring
- `app.py:94-120` Flask POST handling + file upload

### 9. Testing
| Test | Input | Expected | Result |
| T1 | PDF resume + JD | Score 60-80 | Pass |
| T2 | No email in CV | ATS flags ❌ | Pass |
| T3 | Empty CV | Flash error | Pass |
| T4 | Login wrong pwd | Invalid msg | Pass |

### 10. Screenshots (Take from running app)
- Home, Login, Analyze, Result (score 73/100), Dashboard

### 11. Future Enhancement
- BERT embeddings, Resume builder, LinkedIn JD import, PDF report export

### 12. Conclusion
Explainable, offline ATS helper that improves placement readiness.

### 13. References
- scikit-learn TfidfVectorizer docs
- Flask docs
- ATS research papers

### Appendix
- A: `analyser.py` full code
- B: `database/schema.sql`
- C: `requirements.txt`

Page count ~35-45 pages after adding college templates.
