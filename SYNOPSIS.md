# SYNOPSIS - Smart AI Resume Analyzer (ATS Scanner)

**Course:** BCA 3rd Year (6th Sem) Major Project 2026
**Title:** Smart AI Resume Analyzer for Campus Placements
**Team:** [Your Name] - [Roll No]
**Guide:** [Guide Name], Dept. of Computer Applications
**Duration:** 3 Months | **Technology:** Python, Flask, SQLite, NLP (TF-IDF)

### 1. Introduction
Campus placements reject ~70% resumes via Applicant Tracking System (ATS) before human review. Students lack feedback on *why* they were rejected. This project is a web app where students upload resume PDF + paste Job Description and instantly get an ATS score (0-100), skill gaps, and fix suggestions.

### 2. Objectives
- Parse resumes from PDF/DOCX/TXT
- Compute explainable match score (Keyword + Semantic + Skills + ATS)
- Highlight missing skills/keywords to add truthfully
- Store history per student for improvement tracking
- Provide admin view for placement cell

### 3. Scope
- For BCA/B.Tech students targeting IT roles (Python, Java, Web, Data, Cloud)
- Works offline (no OpenAI API), college PC friendly
- Future: BERT scoring, JD scraping, resume builder

### 4. Methodology
`Upload → Text Extraction (PyPDF2) → Tokenize → Skill Extract (70+ DB) → Keyword Score (freq-weighted) + TF-IDF Cosine + Gap + ATS Checks → Weighted Overall → Save SQLite → Report`

Formula: Overall = 40% Keyword + 30% Semantic + 20% Skill + 10% ATS

### 5. System Requirements
- HW: i3+, 4GB RAM
- SW: Python 3.10+, Flask, SQLite, Browser
- Optional: scikit-learn (else Jaccard fallback)

### 6. Modules
1. Auth (Register/Login/Session)
2. Resume Parser
3. JD Analyzer & Skill Extractor
4. Scoring Engine
5. Dashboard & History
6. Admin Panel
7. REST API `/api/analyze`

### 7. Expected Outcome
Student gets: Score, Verdict (Excellent/Good/Moderate/Low), Matched/Missing skills, Top missing keywords, ATS fixes. Avg improvement after 2 edits: +20% score.

### 8. References
- TF-IDF & Cosine Similarity (scikit-learn docs)
- ATS best practices (Jobscan, Resume Worded)

Signature: __________  Date: ________  Guide Sign: __________
