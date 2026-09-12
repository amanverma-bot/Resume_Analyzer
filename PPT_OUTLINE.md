# PPT OUTLINE - 12 Slides (Smart AI Resume Analyzer)

**Slide 1 Title:** Smart AI Resume Analyzer - ATS Scanner for Campus Placements | BCA Final Year 2026 | [Name] | Guide [Name]
**Slide 2 Problem:** 70% resumes rejected by ATS before human | Students have zero feedback | Placement cell manual checking slow
**Slide 3 Solution:** Upload PDF + JD → Instant Score 0-100 + Skill Gap + Keyword fixes | Offline, Free, Explainable
**Slide 4 Objectives:** Parse PDF/DOCX, Explainable scoring, History tracking, Admin view
**Slide 5 Tech Stack:** Python Flask | SQLite | PyPDF2/docx | scikit-learn TF-IDF | HTML/CSS | Diagram
**Slide 6 Architecture + DFD:** Browser → Flask → analyser.py → SQLite ; Show DFD0/DFD1 bubbles
**Slide 7 Scoring Formula:** Overall = 40% Keyword +30% Semantic+20% Skills+10% ATS | Show example: Keyword 65 + Semantic 58 + Skills 40 + ATS 80 → Overall 60.4 → Verdict Moderate
**Slide 8 Features Demo (Screenshots):** Home, Analyze form, Result page (score circle, skill gap red/green), Dashboard table
**Slide 9 Code Snippet:** Show `extract_skills()` and `keyword_match_score()` 15 lines each → explain in viva
**Slide 10 Testing & Results:** Table 4 tests Pass | Demo: Arjun CV vs Python JD → 66% Good match | After adding Docker+K8s → 78% Excellent
**Slide 11 Future Scope:** BERT, JD scraping, Resume builder, Mobile app, Multi-language
**Slide 12 Thank You + Q&A:** Thank guide, Q ready | Contact email

Design: College logo top-right, blue theme, 1 diagram per slide, max 6 bullets.
