#!/usr/bin/env python3
"""
CV Analyser - Analyse resumes/CVs against job descriptions
Features:
  - Parse CV from PDF, DOCX, or TXT
  - Extract contact info, skills, experience, education
  - Keyword/ATS scoring against JD
  - Semantic similarity (if sklearn available, else fallback TF-IDF)
  - Suggestions for missing keywords, formatting, sections
  - JSON + pretty report output
  - Works offline in Termux (no API key needed)

Usage:
  python cv_analyser.py --cv resume.pdf --jd job.txt
  python cv_analyser.py --cv resume.txt --jd job.txt --json
  python cv_analyser.py --demo              # run with built-in demo data
  python cv_analyser.py                     # interactive mode (paste text)

Dependencies (optional but recommended):
  pip install PyPDF2 python-docx scikit-learn
  If not installed, TXT input still works + fallback scoring.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# ---------- Optional deps (graceful fallback) ----------
try:
    import PyPDF2
    HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    import docx
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

# BERT optional (sentence-transformers) - heavy, fallback to TF-IDF if not installed
try:
    from sentence_transformers import SentenceTransformer
    HAS_BERT = True
    _bert_model = None
    def _get_bert():
        global _bert_model
        if _bert_model is None:
            # tiny model, 80MB, best for BCA demo
            _bert_model = SentenceTransformer('all-MiniLM-L6-v2')
        return _bert_model
except ImportError:
    HAS_BERT = False
    _bert_model = None

# ---------- Constants ----------

# Common skill database - expand as needed
SKILLS_DB = [
    # Programming
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust", "ruby", "php", "kotlin", "swift", "sql", "r", "scala", "perl",
    # Web
    "html", "css", "react", "angular", "vue", "node.js", "nodejs", "django", "flask", "fastapi", "spring", "express", "next.js", "tailwind",
    # Data / AI
    "machine learning", "deep learning", "data analysis", "data science", "pandas", "numpy", "tensorflow", "pytorch", "scikit-learn", "nlp", "computer vision", "llm", "generative ai",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "git", "github", "gitlab", "ci/cd", "terraform", "linux", "bash",
    # Databases
    "mysql", "postgresql", "mongodb", "redis", "oracle", "sqlite", "elasticsearch",
    # Soft
    "communication", "leadership", "teamwork", "problem solving", "agile", "scrum", "project management",
    # Other
    "excel", "power bi", "tableau", "figma", "photoshop", "rest api", "graphql", "microservices"
]

# Common sections to check ATS
ATS_SECTIONS = ["contact", "summary", "experience", "education", "skills", "projects", "certifications"]

STOPWORDS = set("""
a an the and or but if in on at to for with of is are was were be been being has have had do does did will would should could
this that these those it its we you your our i me my as by from up into about over after
""".split())

# ---------- Extraction helpers ----------

def read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def read_pdf(path: str) -> str:
    if not HAS_PDF:
        raise ImportError("PyPDF2 not installed. Run: pip install PyPDF2")
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
    return text

def read_docx_file(path: str) -> str:
    if not HAS_DOCX:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)

def load_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    ext = p.suffix.lower()
    if ext == ".pdf":
        return read_pdf(path)
    elif ext == ".docx":
        return read_docx_file(path)
    elif ext in [".txt", ".md", ".rtf", ""]:
        return read_txt(path)
    else:
        # try as text
        return read_txt(path)

def extract_contact(text: str) -> dict:
    email = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    phone = re.findall(r"(\+?\d[\d\s\-\(\)]{8,}\d)", text)
    # crude linkedIn/github
    linkedin = re.findall(r"linkedin\.com\/[^\s]+", text, re.I)
    github = re.findall(r"github\.com\/[^\s]+", text, re.I)
    # clean phones
    phones_clean = []
    for p in phone:
        digits = re.sub(r"\D", "", p)
        if 7 <= len(digits) <= 15:
            phones_clean.append(p.strip())
    return {
        "emails": list(set(email)),
        "phones": list(set(phones_clean))[:3],
        "linkedin": linkedin,
        "github": github
    }

def extract_skills(text: str) -> list:
    low = text.lower()
    found = []
    for s in SKILLS_DB:
        # Use word boundaries, handle special chars like c++, node.js
        pat = r"(?<!\w)" + re.escape(s.lower()) + r"(?!\w)"
        # For skills with dots/slashes, simpler containment
        if any(c in s for c in ["+", ".", "/"]):
            if s.lower() in low:
                found.append(s)
        else:
            if re.search(pat, low):
                found.append(s)
    return sorted(set(found))

def extract_years_experience(text: str) -> float | None:
    # Look for "X years" patterns
    m = re.findall(r"(\d+(?:\.\d+)?)\s*\+?\s*years?[\s\w]*experience", text, re.I)
    if m:
        try:
            return max(float(x) for x in m)
        except:
            pass
    # Look for date ranges 2020-2024 etc to estimate
    dates = re.findall(r"(19|20)\d{2}\s*[-–—to]+\s*(19|20)\d{2}|present|current", text, re.I)
    # Fallback: count work entries
    return None

def detect_sections(text: str) -> dict:
    low = text.lower()
    present = {}
    for sec in ATS_SECTIONS:
        # headings often capitalized or with line breaks
        if re.search(r"\b" + re.escape(sec) + r"\b", low):
            present[sec] = True
        else:
            present[sec] = False
    return present

def ats_checks(text: str, contact: dict, sections: dict) -> list:
    issues = []
    word_count = len(text.split())
    if word_count < 200:
        issues.append(f"⚠️  CV too short ({word_count} words) — aim 400-700 words (1 page) or 700-1000 (2 pages)")
    elif word_count > 1200:
        issues.append(f"⚠️  CV too long ({word_count} words) — recruiters skim; keep to 1-2 pages")
    else:
        issues.append(f"✅ Length OK ({word_count} words)")

    if not contact["emails"]:
        issues.append("❌ Missing email — ATS will reject")
    else:
        issues.append(f"✅ Email found: {contact['emails'][0]}")

    if not contact["phones"]:
        issues.append("⚠️ No phone found — add it in header")

    # Sections
    for sec in ["experience", "education", "skills"]:
        if not sections.get(sec):
            issues.append(f"⚠️ Missing section: '{sec.capitalize()}' heading (ATS expects it)")
        else:
            issues.append(f"✅ Section found: {sec.capitalize()}")

    # File format advice
    if len(re.findall(r"[^\x00-\x7F]", text)) > 20:
        issues.append("⚠️ Many special characters / icons — may break ATS parsing")

    # Bullet points
    bullets = len(re.findall(r"[•\-\*]\s", text))
    if bullets < 3:
        issues.append("⚠️ Few bullet points — use • bullets for achievements (ATS + readability)")

    # Action verbs
    verbs = ["achieved","built","developed","led","managed","created","designed","implemented","improved","increased","reduced","launched","delivered","optimized"]
    found_verbs = [v for v in verbs if re.search(r"\b"+v+r"\b", text.lower())]
    if len(found_verbs) < 3:
        issues.append(f"⚠️ Weak action verbs — add verbs like: {', '.join(verbs[:6])} (found only: {found_verbs or 'none'})")
    else:
        issues.append(f"✅ Strong action verbs: {', '.join(found_verbs[:5])}")

    # Quantifiable results
    nums = re.findall(r"\d+\s*%|\$\s*\d+|\d+\s*(users|clients|projects|clients|revenue|sales)", text, re.I)
    if len(nums) < 2:
        issues.append("⚠️ Add quantifiable achievements (e.g., 'Increased sales 30%', 'Managed 5-member team')")
    else:
        issues.append(f"✅ Quantifiable results found ({len(nums)} hits)")

    return issues

# ---------- Matching / Scoring ----------

def tokenize(text: str) -> list:
    tokens = re.findall(r"[a-zA-Z0-9\+\#\.]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]

def keyword_match_score(cv_text: str, jd_text: str) -> dict:
    cv_tokens = set(tokenize(cv_text))
    jd_tokens = tokenize(jd_text)
    jd_counter = Counter(jd_tokens)
    # Unique JD keywords sorted by frequency
    jd_unique = list(jd_counter.keys())
    
    if not jd_unique:
        return {"score": 0, "matched": [], "missing": [], "total_keywords": 0}

    matched = [k for k in jd_unique if k in cv_tokens]
    missing = [k for k in jd_unique if k not in cv_tokens]

    # Weight by frequency (important JD words matter more)
    total_weight = sum(jd_counter.values())
    matched_weight = sum(jd_counter[k] for k in matched)
    score = (matched_weight / total_weight * 100) if total_weight else 0

    # Sort missing by importance
    missing_sorted = sorted(missing, key=lambda k: jd_counter[k], reverse=True)

    return {
        "score": round(score, 1),
        "matched": matched,
        "missing": missing_sorted,
        "total_keywords": len(jd_unique),
        "matched_count": len(matched),
        "top_jd_keywords": jd_counter.most_common(15)
    }

def semantic_similarity(cv_text: str, jd_text: str) -> float | None:
    if not HAS_SKLEARN:
        return None
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1,2)).fit([cv_text, jd_text])
        tfidf = vec.transform([cv_text, jd_text])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0] * 100
        return round(float(sim), 1)
    except:
        return None

def bert_semantic_similarity(cv_text: str, jd_text: str) -> tuple[float | None, str]:
    """Try BERT (MiniLM) first, else TF-IDF, else Jaccard. Returns (score, method)."""
    if HAS_BERT:
        try:
            model = _get_bert()
            import numpy as np
            embs = model.encode([cv_text, jd_text], normalize_embeddings=True)
            # cosine = dot for normalized
            sim = float(np.dot(embs[0], embs[1]) * 100)
            return round(sim, 1), "BERT all-MiniLM-L6-v2 (sentence-transformers)"
        except Exception as e:
            pass
    # fallback to TF-IDF
    s = semantic_similarity(cv_text, jd_text)
    if s is not None:
        return s, "TF-IDF cosine (scikit-learn) — install sentence-transformers for BERT"
    return fallback_similarity(cv_text, jd_text), "Jaccard (fallback — pip install scikit-learn sentence-transformers for better)"

def fallback_similarity(cv_text: str, jd_text: str) -> float:
    # Jaccard on tokens
    a = set(tokenize(cv_text))
    b = set(tokenize(jd_text))
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return round(inter / union * 100, 1)

def skill_gap(cv_skills: list, jd_skills: list) -> dict:
    cv_s = set(s.lower() for s in cv_skills)
    jd_s = set(s.lower() for s in jd_skills)
    matched = sorted(cv_s & jd_s)
    missing = sorted(jd_s - cv_s)
    extra = sorted(cv_s - jd_s)
    coverage = (len(matched) / len(jd_s) * 100) if jd_s else 100
    return {
        "matched": matched,
        "missing": missing,
        "extra": extra,
        "coverage": round(coverage, 1)
    }

def overall_score(keyword_score: float, semantic: float | None, skill_coverage: float, sections: dict, contact_ok: bool) -> float:
    # Weighting: 40% keyword, 30% semantic, 20% skills, 10% ATS structure
    sem = semantic if semantic is not None else keyword_score  # fallback
    ats_score = sum(sections.values()) / len(sections) * 100 if sections else 50
    if not contact_ok:
        ats_score *= 0.7
    total = keyword_score * 0.4 + sem * 0.3 + skill_coverage * 0.2 + ats_score * 0.1
    return round(total, 1)

def verdict(score: float) -> str:
    if score >= 80:
        return "🟢 Excellent match — Ready to apply!"
    if score >= 65:
        return "🟡 Good match — Fix missing keywords & re-apply"
    if score >= 45:
        return "🟠 Moderate — Needs tailoring for this JD"
    return "🔴 Low match — Major rewrite needed for this role"

# ---------- Main analyse ----------

def analyse(cv_text: str, jd_text: str) -> dict:
    cv_skills = extract_skills(cv_text)
    jd_skills = extract_skills(jd_text)

    contact = extract_contact(cv_text)
    sections = detect_sections(cv_text)
    ats = ats_checks(cv_text, contact, sections)

    kw = keyword_match_score(cv_text, jd_text)
    sem, sem_method = bert_semantic_similarity(cv_text, jd_text)

    gap = skill_gap(cv_skills, jd_skills)
    contact_ok = bool(contact["emails"])
    total = overall_score(kw["score"], sem, gap["coverage"], sections, contact_ok)

    return {
        "meta": {
            "analysed_at": datetime.now().isoformat(),
            "cv_words": len(cv_text.split()),
            "jd_words": len(jd_text.split()),
            "method": sem_method
        },
        "contact": contact,
        "sections": sections,
        "skills": {
            "cv_skills": cv_skills,
            "jd_skills": jd_skills,
            "gap": gap
        },
        "scores": {
            "overall": total,
            "verdict": verdict(total),
            "keyword_match": kw["score"],
            "semantic_similarity": sem,
            "skill_coverage": gap["coverage"]
        },
        "keywords": kw,
        "ats_checks": ats
    }

def ai_build_cv(data: dict) -> str:
    """Build ATS-safe CV from form data with AI polish (no API key)."""
    name = data.get("name","").strip() or "YOUR NAME"
    email = data.get("email","").strip()
    phone = data.get("phone","").strip()
    loc = data.get("location","").strip()
    linkedin = data.get("linkedin","").strip()
    github = data.get("github","").strip()
    jd = data.get("jd","").strip()
    summary_in = data.get("summary","").strip()
    edu = data.get("education","").strip()
    skills_in = data.get("skills","").strip()
    exp_in = data.get("experience","").strip()
    proj_in = data.get("projects","").strip()
    certs = data.get("certs","").strip()

    # header
    header = name.upper()
    contact_parts = [p for p in [email, phone, loc] if p]
    contact_line = " | ".join(contact_parts)
    links = " | ".join([p for p in [linkedin, github] if p])

    # polish summary via AI logic
    if not summary_in:
        # generate tailored summary
        skills_list = [s.strip() for s in skills_in.split(",") if s.strip()]
        role = "Software Developer"
        if jd:
            m = re.search(r"(Python|Java|React|Frontend|Backend|Full Stack|Data|DevOps|ML)[^\n]{0,30}", jd, re.I)
            if m: role = m.group(0).strip()[:50]
        summary_in = f"Motivated {role} with hands-on experience in {', '.join(skills_list[:4]) or 'modern tech'}. Built projects with {', '.join(skills_list[:3]) or 'Python, React'} and solved real problems. Seeking to contribute {', '.join(extract_skills(jd)[:3]) or 'technical skills'} in an Agile team. Strong in problem solving and teamwork."
        if jd:
            jd_sk = extract_skills(jd)[:3]
            if jd_sk:
                summary_in = summary_in.replace(".", f" aligned with {', '.join(jd_sk)}.", 1)

    # polish experience: ensure bullets, verbs, metrics
    exp_lines = [l.strip() for l in exp_in.split("\n") if l.strip()]
    polished_exp = []
    verbs = ["Built","Developed","Implemented","Designed","Optimized","Delivered"]
    for i, line in enumerate(exp_lines):
        if not line.startswith("-") and not line.startswith("•"):
            # add bullet if not present
            if re.match(r"^[A-Z][a-z]+,.*\d{4}", line):
                polished_exp.append(line)  # header like Intern, Tech — date
            else:
                # polish bullet
                has_metric = bool(re.search(r"\d+%|\d+ users", line, re.I))
                metric = f", improving performance by {20+i*5}%" if not has_metric and i<len(exp_lines)-1 else ""
                v = verbs[i % len(verbs)]
                if not re.match(r"^(Built|Developed|Implemented|Designed|Created|Managed)", line, re.I):
                    line = f"{v} {line[0].lower()+line[1:]}"
                polished_exp.append(f"• {line}{metric}")
        else:
            polished_exp.append(line if line.startswith("•") else line.replace("-", "•", 1))

    # polish projects similarly
    proj_lines = [l.strip() for l in proj_in.split("\n") if l.strip()]
    polished_proj = []
    for p in proj_lines:
        if not p.startswith("•") and not p.startswith("-"):
            # ensure tech mention
            polished_proj.append(f"• {p}")
        else:
            polished_proj.append(p if p.startswith("•") else p.replace("-", "•",1))

    # skills: ensure comma clean + add JD missing as Familiar if jd provided
    skills_clean = ", ".join([s.strip() for s in skills_in.split(",") if s.strip()])
    if jd:
        jd_missing = skill_gap(extract_skills(skills_clean), extract_skills(jd))["missing"][:3]
        if jd_missing:
            extra = ", ".join([f"{m} (Familiar)" for m in jd_missing])
            skills_clean = skills_clean + (", " + extra if skills_clean else extra)

    # assemble ATS-safe
    sections = []
    sections.append(header)
    if contact_line: sections.append(contact_line)
    if links: sections.append(links)
    sections.append("")
    sections.append("SUMMARY")
    sections.append(summary_in)
    sections.append("")
    sections.append("EDUCATION")
    sections.append(edu or "BCA, [College] — 2022-2025")
    sections.append("")
    sections.append("EXPERIENCE")
    sections.extend(polished_exp or ["• Built projects with Python and React"])
    sections.append("")
    sections.append("PROJECTS")
    sections.extend(polished_proj or ["• E-Commerce Clone — React, Node.js"])
    sections.append("")
    sections.append("SKILLS")
    sections.append(skills_clean or "Python, SQL, Git")
    if certs:
        sections.append("")
        sections.append("CERTIFICATIONS")
        sections.append(certs)
    return "\n".join(sections).strip()

def ai_cover_letter(cv_text: str, jd_text: str, data: dict = None) -> str:
    """Generate tailored cover letter (no API key, ATS-friendly)."""
    data = data or {}
    name = data.get("name","") or re.findall(r"^([A-Z][a-z]+ [A-Z][a-z]+)", cv_text, re.M)[:1]
    name = name[0] if isinstance(name, list) and name else (name if isinstance(name, str) else "Applicant")
    if isinstance(name, list): name = name[0]
    # extract company/role from JD
    company = re.search(r"(?:at|@|company:?)\s*([A-Z][\w &]+(?:Pvt|Inc|LLC|Ltd)?)", jd_text, re.I)
    company = company.group(1).strip()[:40] if company else "your organization"
    role = re.search(r"(Python|Java|React|Frontend|Backend|Full Stack|Data|DevOps|ML|Developer|Engineer)[^\n]{0,40}", jd_text, re.I)
    role = role.group(0).strip()[:60] if role else "this role"
    # skills
    cv_sk = extract_skills(cv_text)[:5]
    jd_sk = extract_skills(jd_text)[:5]
    matched = skill_gap(cv_sk, jd_sk)["matched"][:4]
    # contact
    contact = extract_contact(cv_text)
    email = (contact["emails"][:1] or [""])[0]
    phone = (contact["phones"][:1] or [""])[0]
    today = datetime.now().strftime("%B %d, %Y")
    # build letter
    letter = f"""{name}
{email + " | " if email else ""}{phone}
{today}

Hiring Manager
{company}

Subject: Application for {role}

Dear Hiring Manager,

I am excited to apply for the {role} at {company}. With hands-on experience in {', '.join(matched) or ', '.join(cv_sk[:3]) or 'Python, React, SQL'}, I have built projects that mirror your requirements such as "{jd_text.strip().split(chr(10))[0][:120]}...".

Highlights matching your JD:
"""
    # bullets from CV
    bullets = re.findall(r"[-•]\s*(.+)", cv_text)[:3]
    if not bullets:
        bullets = [f"Built solutions with {', '.join(cv_sk[:3]) or 'modern stack'} with measurable impact"]
    for b in bullets:
        letter += f"• {b.strip()[:140]}\n"
    letter += f"""
What I bring to {company}:
• Strong in {', '.join(matched) or ', '.join(jd_sk[:3]) or 'core tech'} — eager to contribute to {', '.join(jd_sk[:2]) or 'scalable systems'}.
• Collaborative in Agile teams, quick learner for {', '.join(skill_gap(cv_sk, jd_sk)['missing'][:2]) or 'new stack'} (Familiar, with hands-on labs).
• ATS-aware communication: concise, metrics-driven, clean code.

I would love to discuss how I can help {company} build {jd_sk[0] if jd_sk else 'impactful products'}. Thank you for considering my application. I am available for an interview at your convenience.

Sincerely,
{name}
"""
    return letter.strip()

def fetch_jd_from_url(url: str, timeout: int = 10) -> str:
    """Fetch JD text from URL (LinkedIn/Naukri/generic). No API key."""
    if not url or not re.match(r"https?://", url, re.I):
        return ""
    # basic SSRF guard: only http/https
    try:
        import urllib.request, urllib.error
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (ResumePro AI BCA)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            # naive extract: remove scripts/styles, get text between <p> <li> <div>
            # strip tags
            text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.I|re.S)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            # keep first 4000 chars
            return text[:4000]
    except Exception as e:
        return f""

def generate_mock_questions(cv_text: str, jd_text: str, n: int = 7) -> list:
    """Generate tailored mock interview Qs (no API key). Returns list of dicts."""
    cv_sk = extract_skills(cv_text)
    jd_sk = extract_skills(jd_text)
    gap = skill_gap(cv_sk, jd_sk)
    matched = gap["matched"]
    missing = gap["missing"]
    # extract projects
    proj_lines = [l.strip() for l in cv_text.split("\n") if re.search(r"project|clone|tool|app", l, re.I)][:2]
    proj = proj_lines[0][:80] if proj_lines else "your main project"

    qs = []
    # 1-2 Technical (matched + missing)
    if matched:
        qs.append({"q": f"Explain your experience with {matched[0]} — where did you use it and what challenges did you face?", "type":"Technical", "keywords": [matched[0], "project", "challenge"], "tip": f"Mention project where you used {matched[0]} with STAR + metric"})
    if len(matched)>1:
        qs.append({"q": f"How would you build a REST API using {matched[1] if len(matched)>1 else 'your stack'}? Walk through your approach.", "type":"Technical", "keywords": [matched[1] if len(matched)>1 else "api", "rest", "database"], "tip":"Cover design, DB, auth, deployment"})
    if missing:
        qs.append({"q": f"JD requires {missing[0]} which is not in your resume — how would you ramp up quickly?", "type":"Technical (Gap)", "keywords": [missing[0], "learn", "project"], "tip":"Show learning plan + mini-project, honesty about Familiar"})
    # Behavioral
    qs.append({"q": "Tell me about a time you optimized performance or solved a critical bug.", "type":"Behavioral (STAR)", "keywords": ["situation","action","result","percent","improved"], "tip":"Use STAR, add % metric"})
    qs.append({"q": f"Describe {proj} — your role, tech stack, and impact.", "type":"Project Deep-Dive", "keywords": ["role","tech","impact","users"], "tip":"Quantify users/load time"})
    # HR
    qs.append({"q": "Why do you want to join our company for this role?", "type":"HR", "keywords": ["company","role","skills","contribute"], "tip":"Mirror JD phrasing, show you read JD"})
    if len(qs) < n:
        qs.append({"q": "Where do you see yourself in 2 years and how does this role help?", "type":"HR", "keywords": ["growth","learn","contribute"], "tip":"Link personal growth to company growth"})

    # trim/pad
    return qs[:n]

def evaluate_answer(question: dict, answer: str) -> dict:
    """Score answer 0-10 based on keyword coverage, STAR, length."""
    if not answer or len(answer.strip())<10:
        return {"score": 0, "feedback": "Too short — aim 4-6 lines with STAR.", "level":"Weak"}
    ans_low = answer.lower()
    kws = [k.lower() for k in question.get("keywords",[])]
    matched = sum(1 for k in kws if k in ans_low)
    kw_score = (matched/len(kws)*5) if kws else 2.5
    # STAR check
    star_words = ["situation","task","action","result","achieved","built","improved","resulted","impact"]
    star_hit = sum(1 for w in star_words if w in ans_low)
    star_score = min(2, star_hit*0.5)
    # length & metric
    length_score = 1.5 if 80 < len(answer) < 600 else 1 if len(answer)>40 else 0.5
    metric_bonus = 1 if re.search(r"\d+%|\d+ users|\d+ members", answer, re.I) else 0
    total = round(min(10, kw_score + star_score + length_score + metric_bonus), 1)
    if total >= 8: level, fb = "Excellent", "Strong STAR + keywords + metric — interview-ready!"
    elif total >= 6: level, fb = "Good", "Add a metric (%, users) and one JD keyword to reach 8+"
    elif total >= 4: level, fb = "Moderate", f"Missing keywords: {', '.join([k for k in kws if k not in ans_low][:2]) or 'add STAR'}. Expand to 4-5 lines."
    else: level, fb = "Weak", "Use STAR: Situation → Action → Result, and weave JD keywords."
    return {"score": total, "feedback": fb, "level": level, "matched_kw": matched, "total_kw": len(kws)}

# ---------- AI Enhance (local, no API key) ----------
def ai_enhance_cv(cv_text: str, jd_text: str, res: dict) -> dict:
    """
    Rule-based CV enhancer that *simulates* AI rewrite:
    - Generates tailored summary
    - Injects missing skills truthfully (with 'Familiar with' guard)
    - Rewrites bullets with STAR + keywords
    - Predicts new score if enhancements applied
    """
    gap = res["skills"]["gap"]
    missing = gap["missing"][:6]
    matched = gap["matched"]
    kw_missing = res["keywords"]["missing"][:8]

    # Detect role from JD (first noun phrase)
    role_match = re.search(r"(Python|Java|React|Frontend|Backend|Full Stack|Data|DevOps|ML|Developer|Engineer)[^\n]{0,40}", jd_text, re.I)
    role = role_match.group(0).strip()[:60] if role_match else "Target Role"

    # 1) Enhanced Summary
    cv_skills_str = ", ".join(matched[:5]) if matched else "relevant tech stack"
    exp_years = extract_years_experience(cv_text) or "1+"
    enhanced_summary = (
        f"Motivated {role} with {exp_years} years of hands-on experience in {cv_skills_str}. "
        f"Proven ability to build scalable solutions using {', '.join(matched[:4]) or 'modern technologies'} "
        f"and collaborate in Agile teams. "
        f"Eager to leverage expertise in {', '.join(missing[:3]) or 'emerging tech'} to deliver impact at your organization. "
        f"Strong in {', '.join(kw_missing[:3]) or 'problem solving'}."
    )

    # 2) Enhanced Skills line (merge + missing)
    existing_skills = res["skills"]["cv_skills"]
    # Add missing with honest prefix if not proven
    enhanced_skills = existing_skills + [f"{m} (Familiar)" for m in missing if m not in [s.lower() for s in existing_skills]]
    enhanced_skills_line = ", ".join(sorted(set(enhanced_skills), key=str.lower))

    # 3) Bullet improvements
    # Find existing bullets
    raw_bullets = re.findall(r"[-•]\s*(.+)", cv_text)
    if not raw_bullets:
        # fallback: take experience lines
        raw_bullets = [l.strip() for l in cv_text.split("\n") if len(l.strip())>30][:4]

    action_verbs = ["Built","Developed","Implemented","Designed","Optimized","Launched","Delivered","Improved"]
    enhanced_bullets = []
    for i, b in enumerate(raw_bullets[:5]):
        b_clean = b.strip().rstrip(".")
        # Inject keyword if bullet lacks it
        inject = kw_missing[i % len(kw_missing)] if kw_missing else ""
        # Add metric if missing
        has_metric = bool(re.search(r"\d+%|\d+ users|\d+ members", b_clean, re.I))
        metric = f", improving {['performance','efficiency','load time','user engagement'][i%4]} by {20+i*5}%" if not has_metric else ""
        verb = action_verbs[i % len(action_verbs)]
        if not re.match(r"^(Built|Developed|Implemented|Designed|Created|Managed|Led)", b_clean, re.I):
            b_clean = f"{verb} {b_clean[0].lower()+b_clean[1:]}" if b_clean else b_clean
        if inject and inject.lower() not in b_clean.lower():
            b_clean = f"{b_clean} using {inject}"
        enhanced_bullets.append(f"• {b_clean}{metric}.")

    if missing:
        enhanced_bullets.append(f"• Explored {', '.join(missing[:3])} through hands-on labs and personal projects (Familiar level) to align with JD requirements.")

    # 4) ATS fixes checklist
    fixes = []
    if not res["sections"].get("summary"):
        fixes.append("Added tailored 3-line Summary at top (mirrors JD phrasing)")
    if missing:
        fixes.append(f"Added missing skills: {', '.join(missing[:4])} (marked Familiar if not certified)")
    if kw_missing:
        fixes.append(f"Wove keywords into bullets: {', '.join(kw_missing[:5])}")
    if len(re.findall(r"\d+\s*%|\d+ users", cv_text, re.I)) < 2:
        fixes.append("Quantified 2-3 bullets with metrics (%, users)")
    fixes.append("Ensured ATS-safe headings: Summary, Experience, Education, Skills, Projects")

    # 5) Simulate new score (boost proportional to fixes)
    boost = min(25, len(missing)*3 + len(kw_missing)*1.5 + (0 if res["sections"].get("summary") else 5))
    predicted = min(95, res["scores"]["overall"] + boost)
    predicted = round(predicted, 1)

    # 6) Build full enhanced CV text
    contact = res["contact"]
    # Keep original header (first 3 lines)
    lines = cv_text.strip().split("\n")
    header = "\n".join(lines[:3]) if len(lines) >=3 else lines[0] if lines else ""
    # Try to preserve name/email line
    enhanced_full = f"""{header}

SUMMARY
{enhanced_summary}

EXPERIENCE
""" + "\n".join(enhanced_bullets) + f"""

SKILLS
{enhanced_skills_line}

EDUCATION
""" + "\n".join([l for l in lines if re.search(r"B\.?Tech|BCA|University|CGPA|%", l, re.I)][:3]) + f"""

PROJECTS
• Built E-Commerce microservices with {', '.join(matched[:3]) or 'React, Node.js'} — handled cart & payments for 500+ test users
• {f'Integrated {missing[0]} stack' if missing else 'Optimized app performance'} for college fest — improved load time 30%

CERTIFICATIONS
• Add: {', '.join(missing[:2]) + ' — Coursera/ Udemy (in progress)' if missing else 'AWS Cloud Practitioner'}
"""
    return {
        "role": role,
        "enhanced_summary": enhanced_summary,
        "enhanced_skills_line": enhanced_skills_line,
        "enhanced_bullets": enhanced_bullets,
        "fixes": fixes,
        "predicted_score": predicted,
        "boost": round(boost,1),
        "enhanced_full": enhanced_full.strip(),
        "missing_injected": missing,
        "keywords_injected": kw_missing
    }

def pretty_report(res: dict, cv_text: str, jd_text: str) -> str:
    s = res["scores"]
    kw = res["keywords"]
    gap = res["skills"]["gap"]
    lines = []
    lines.append("="*70)
    lines.append("📄 CV ANALYSER REPORT")
    lines.append(f"🕒 {res['meta']['analysed_at'][:19]} | CV words: {res['meta']['cv_words']} | JD words: {res['meta']['jd_words']}")
    lines.append("="*70)
    lines.append("")
    lines.append(f"⭐ OVERALL MATCH: {s['overall']}/100 — {s['verdict']}")
    lines.append("")
    lines.append(f"  • Keyword Match      : {s['keyword_match']}% ({kw['matched_count']}/{kw['total_keywords']} JD keywords matched)")
    lines.append(f"  • Semantic Similarity: {s['semantic_similarity']}% [{res['meta']['method']}]")
    lines.append(f"  • Skill Coverage     : {s['skill_coverage']}% ({len(gap['matched'])}/{len(res['skills']['jd_skills']) or 1} skills)")
    lines.append("")

    # Contact
    lines.append("-"*70)
    lines.append("📇 CONTACT & ATS STRUCTURE")
    lines.append("-"*70)
    c = res["contact"]
    lines.append(f"Emails : {', '.join(c['emails']) or '❌ NOT FOUND'}")
    lines.append(f"Phones : {', '.join(c['phones']) or '❌ NOT FOUND'}")
    lines.append(f"Links  : LinkedIn={bool(c['linkedin'])} GitHub={bool(c['github'])}")
    sec = res["sections"]
    present = [k for k,v in sec.items() if v]
    missing_sec = [k for k,v in sec.items() if not v]
    lines.append(f"Sections present : {', '.join(present) or 'none'}")
    if missing_sec:
        lines.append(f"Sections missing : {', '.join(missing_sec)}")

    lines.append("")
    for chk in res["ats_checks"]:
        lines.append("  " + chk)

    # Skills
    lines.append("")
    lines.append("-"*70)
    lines.append("🛠️ SKILLS GAP ANALYSIS")
    lines.append("-"*70)
    lines.append(f"CV skills ({len(res['skills']['cv_skills'])}): {', '.join(res['skills']['cv_skills']) or 'none detected'}")
    lines.append(f"JD requires ({len(res['skills']['jd_skills'])}): {', '.join(res['skills']['jd_skills']) or 'no tech skills detected (soft-role?)'}")
    lines.append("")
    if gap["matched"]:
        lines.append(f"✅ Matched skills: {', '.join(gap['matched'])}")
    if gap["missing"]:
        lines.append(f"❌ Missing skills (ADD these): {', '.join(gap['missing'])}")
    if gap["extra"]:
        lines.append(f"ℹ️ Extra skills (nice to have): {', '.join(gap['extra'][:10])}")

    # Keywords
    lines.append("")
    lines.append("-"*70)
    lines.append("🔑 KEYWORD ANALYSIS (Top JD keywords)")
    lines.append("-"*70)
    top = kw["top_jd_keywords"][:12]
    lines.append("Top JD keywords (freq): " + ", ".join(f"{k}({v})" for k,v in top))
    lines.append("")
    if kw["matched"]:
        lines.append(f"✅ Matched ({len(kw['matched'])}): {', '.join(kw['matched'][:30])}")
    if kw["missing"]:
        lines.append(f"❌ Missing (top 25 by importance): {', '.join(kw['missing'][:25])}")

    # Actionable suggestions
    lines.append("")
    lines.append("-"*70)
    lines.append("💡 ACTIONABLE FIXES (Do these before applying)")
    lines.append("-"*70)
    suggestions = []
    if gap["missing"]:
        suggestions.append(f"1. Add missing skills to Skills/Project sections: {', '.join(gap['missing'][:6])} — only if truthful; add proof (project/cert).")
    if kw["missing"]:
        suggestions.append(f"2. Weave missing JD keywords naturally into Experience bullets: {', '.join(kw['missing'][:8])}.")
    if not sec.get("summary"):
        suggestions.append("3. Add 3-line Summary at top tailored to JD (role + years + 2-3 key skills).")
    if s["overall"] < 65:
        suggestions.append("4. Tailor 3-4 bullet points per job to mirror JD phrasing (e.g., JD says 'REST API' not 'APIs').")
    suggestions.append("5. Keep formatting ATS-safe: no tables/images, use simple headings (Experience, Education, Skills), export as PDF text-selectable.")
    suggestions.append("6. Quantify: add numbers to 2-3 bullets (%, users, revenue, time saved).")
    
    for sugg in suggestions:
        lines.append("  • " + sugg)

    lines.append("")
    lines.append("="*70)
    lines.append("Tip: Re-run after edits to watch Overall climb to 75%+")
    lines.append("="*70)
    return "\n".join(lines)

# ---------- CLI ----------

DEMO_CV = """
ARJUN SHARMA
Email: arjun.sharma@email.com | Phone: +91 98765 43210 | LinkedIn: linkedin.com/in/arjunsharma | GitHub: github.com/arjunsharma
Location: Pune, India

SUMMARY
Aspiring Software Engineer with 1 year internship experience building web apps with Python and React. Passionate about clean code and problem solving.

EDUCATION
B.Tech Computer Science, Pune University — 2021-2025, CGPA 8.2

EXPERIENCE
Software Intern, Tech Solutions Pvt Ltd — Jun 2024 - Dec 2024
- Built REST API with Flask and PostgreSQL for 500+ users
- Developed React dashboard, improved load time by 30%
- Implemented Git CI/CD and Docker deployment

PROJECTS
E-Commerce Clone — React, Node.js, MongoDB — Built cart and payment flow
Data Analysis Tool — Python, Pandas, Tableau — Visualized sales data for college fest

SKILLS
Python, JavaScript, React, Flask, Git, SQL, PostgreSQL, Docker, HTML, CSS, MongoDB

CERTIFICATIONS
AWS Cloud Practitioner (2024)
"""

DEMO_JD = """
We are hiring a Junior Python Developer (Immediate Joiner) — Pune
Requirements:
- Strong Python, Django or Flask, REST API development
- Frontend: React or Angular, HTML, CSS, JavaScript
- Databases: PostgreSQL, MySQL or MongoDB
- Cloud: AWS or GCP, Docker, Kubernetes, CI/CD
- Good communication, teamwork, problem solving, Agile
- Preferred: Machine Learning, Pandas, NumPy, 1+ years experience
- Build scalable microservices, write clean code, manage Git

Responsibilities: Develop microservices, build REST APIs, work with Docker/Kubernetes on AWS, collaborate in Agile team.
"""

def interactive():
    print("📄 CV Analyser — Interactive Mode")
    print("="*60)
    print("Paste CV text OR enter path to file (.pdf/.docx/.txt).")
    print("Type 'demo' for built-in example, or 'quit' to exit.")
    print()

    def get_input(prompt: str) -> str:
        print(prompt)
        print("(End with a line containing only ::: then Enter)")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == ":::": 
                break
            if line.strip().lower() in ["quit", "exit"] and not lines:
                return line
            lines.append(line)
        text = "\n".join(lines).strip()
        # If it's a file path, try to load
        if len(lines) == 1 and Path(text).exists():
            try:
                return load_file(text)
            except Exception as e:
                print(f"Could not read file: {e}")
                return text
        return text

    while True:
        cv = get_input("▶ STEP 1: Paste CV text / file path (or type demo):")
        if cv.lower().strip() in ["quit", "exit"]:
            break
        if cv.lower().strip() == "demo":
            cv, jd = DEMO_CV, DEMO_JD
            print("\n--- Using DEMO CV + JD ---\n")
        else:
            if len(cv.strip()) < 50:
                print("⚠️ CV too short, paste more content or try demo")
                continue
            jd = get_input("\n▶ STEP 2: Paste JOB DESCRIPTION text / file path:")
            if jd.lower().strip() in ["quit", "exit"]:
                break
            if len(jd.strip()) < 20:
                print("⚠️ JD too short")
                continue
        res = analyse(cv, jd)
        print("\n" + pretty_report(res, cv, jd) + "\n")
        
        save = input("Save report to file? (json/txt/n = no) [n]: ").strip().lower()
        if save in ["json", "j"]:
            out = f"cv_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(res, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved JSON to {out}")
        elif save in ["txt", "t"]:
            out = f"cv_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(out, "w", encoding="utf-8") as f:
                f.write(pretty_report(res, cv, jd))
            print(f"✅ Saved TXT to {out}")
        
        again = input("\nAnalyse another? y/n [y]: ").strip().lower()
        if again == "n":
            break

def main():
    p = argparse.ArgumentParser(description="CV Analyser — match CV against Job Description")
    p.add_argument("--cv", help="Path to CV file (pdf/docx/txt)")
    p.add_argument("--jd", help="Path to JD file (txt/pdf/docx) or raw JD string if --jd-text")
    p.add_argument("--jd-text", help="Pass JD directly as text (wrap in quotes)")
    p.add_argument("--cv-text", help="Pass CV directly as text")
    p.add_argument("--json", action="store_true", help="Output JSON instead of pretty report")
    p.add_argument("--out", help="Save report to file (auto detects json/txt from extension)")
    p.add_argument("--demo", action="store_true", help="Run demo with sample CV+JD")
    args = p.parse_args()

    if args.demo:
        res = analyse(DEMO_CV, DEMO_JD)
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(pretty_report(res, DEMO_CV, DEMO_JD))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                if args.out.endswith(".json"):
                    json.dump(res, f, indent=2, ensure_ascii=False)
                else:
                    f.write(pretty_report(res, DEMO_CV, DEMO_JD))
            print(f"\n✅ Saved to {args.out}", file=sys.stderr)
        return

    cv_text = None
    jd_text = None

    if args.cv_text:
        cv_text = args.cv_text
    elif args.cv:
        cv_text = load_file(args.cv)

    if args.jd_text:
        jd_text = args.jd_text
    elif args.jd:
        # If file exists, load; else treat as raw text
        if Path(args.jd).exists():
            jd_text = load_file(args.jd)
        else:
            jd_text = args.jd

    if cv_text and jd_text:
        res = analyse(cv_text, jd_text)
        if args.json:
            output = json.dumps(res, indent=2, ensure_ascii=False)
            print(output)
        else:
            print(pretty_report(res, cv_text, jd_text))
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                if args.out.endswith(".json"):
                    json.dump(res, f, indent=2, ensure_ascii=False)
                else:
                    f.write(pretty_report(res, cv_text, jd_text))
            print(f"\n✅ Saved to {args.out}", file=sys.stderr)
        return

    # No args -> interactive
    if not cv_text or not jd_text:
        interactive()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBye! 👋")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        sys.exit(1)
