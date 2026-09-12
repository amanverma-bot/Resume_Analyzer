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
    sem = semantic_similarity(cv_text, jd_text)
    if sem is None:
        sem_fallback = fallback_similarity(cv_text, jd_text)
        sem = sem_fallback
        sem_method = "jaccard (fallback — install scikit-learn for better TF-IDF)"
    else:
        sem_method = "TF-IDF cosine (scikit-learn)"

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
