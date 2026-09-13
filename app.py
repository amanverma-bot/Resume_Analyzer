#!/usr/bin/env python3
"""
BCA Final Year Project: Smart AI Resume Analyzer (ATS Scanner)
Flask Web App with Login + SQLite History
Run: pip install flask PyPDF2 python-docx scikit-learn
     python app.py
Open: http://127.0.0.1:5000
"""
import os, sqlite3, json
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, send_file, jsonify, make_response
import analyser as core
import io

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bca-final-year-2026-secret-key-change-in-prod")
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
DATABASE = 'database/app.db'

# ---------- DB ----------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS analyses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            overall REAL,
            verdict TEXT,
            keyword_score REAL,
            semantic REAL,
            skill_coverage REAL,
            cv_skills TEXT,
            jd_skills TEXT,
            missing_skills TEXT,
            cv_text TEXT,
            jd_text TEXT,
            result_json TEXT,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        # create default admin
        cur = conn.execute("SELECT id FROM users WHERE username='admin'")
        if not cur.fetchone():
            conn.execute("INSERT INTO users(username,password,email,created_at) VALUES(?,?,?,?)",
                         ('admin','admin123','admin@college.edu', datetime.now().isoformat()))
            conn.commit()

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, '_database', None)
    if db: db.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login required')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ---------- Helpers ----------
def extract_text_from_upload(file_storage):
    if not file_storage or not file_storage.filename:
        return ""
    fname = file_storage.filename
    ext = Path(fname).suffix.lower()
    # save temp
    tmp = os.path.join(app.config['UPLOAD_FOLDER'], fname)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    file_storage.save(tmp)
    try:
        if ext == ".pdf":
            return core.read_pdf(tmp)
        elif ext == ".docx":
            return core.read_docx_file(tmp)
        else:
            return Path(tmp).read_text(encoding="utf-8", errors="ignore")
    finally:
        # keep file for reference maybe, but not needed
        pass

# ---------- Routes ----------
@app.route("/")
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template("index.html", demo_cv=core.DEMO_CV.strip(), demo_jd=core.DEMO_JD.strip())

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        e = request.form.get("email","").strip()
        if not u or not p:
            flash("Username & password required")
            return redirect(url_for("register"))
        try:
            with sqlite3.connect(DATABASE) as conn:
                conn.execute("INSERT INTO users(username,password,email,created_at) VALUES(?,?,?,?)",
                             (u,p,e, datetime.now().isoformat()))
                conn.commit()
            flash("Registered! Please login")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        with sqlite3.connect(DATABASE) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u,p)).fetchone()
            if row:
                session['user_id'] = row['id']
                session['username'] = row['username']
                return redirect(url_for('dashboard'))
        flash("Invalid credentials (try admin/admin123)")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    rows = db.execute("SELECT * FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 20", (session['user_id'],)).fetchall()
    # stats
    total = db.execute("SELECT COUNT(*) FROM analyses WHERE user_id=?", (session['user_id'],)).fetchone()[0]
    avg = db.execute("SELECT AVG(overall) FROM analyses WHERE user_id=?", (session['user_id'],)).fetchone()[0]
    return render_template("dashboard.html", history=rows, total=total, avg=round(avg or 0,1))

@app.route("/cover-letter", methods=["GET","POST"])
def cover_letter():
    # allow guest but save if logged in
    if request.method == "GET":
        # prefill from last analysis if exists
        cv_pref = core.DEMO_CV.strip()
        jd_pref = core.DEMO_JD.strip()
        if 'user_id' in session:
            db = get_db()
            row = db.execute("SELECT cv_text, jd_text FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 1", (session['user_id'],)).fetchone()
            if row:
                cv_pref = row['cv_text'][:2000]
                jd_pref = row['jd_text'][:1500]
        return render_template("cover_letter.html", cv_text=cv_pref, jd_text=jd_pref)
    cv_text = request.form.get("cv_text","").strip()
    jd_text = request.form.get("jd_text","").strip()
    jd_url = request.form.get("jd_url","").strip()
    if jd_url and len(jd_text)<30:
        fetched = core.fetch_jd_from_url(jd_url)
        if fetched: jd_text = fetched
        else: flash("Could not fetch URL — paste JD text manually")
    name = request.form.get("name","").strip()
    if not cv_text or not jd_text:
        flash("CV and JD required"); return redirect(url_for('cover_letter'))
    letter = core.ai_cover_letter(cv_text, jd_text, {"name": name})
    # optionally save? not needed
    return render_template("cover_letter_result.html", letter=letter, cv_text=cv_text, jd_text=jd_text)

@app.route("/mock-interview", methods=["GET","POST"])
def mock_interview():
    if request.method == "GET":
        cv_pref = core.DEMO_CV.strip()
        jd_pref = core.DEMO_JD.strip()
        if 'user_id' in session:
            db = get_db()
            row = db.execute("SELECT cv_text, jd_text FROM analyses WHERE user_id=? ORDER BY id DESC LIMIT 1", (session['user_id'],)).fetchone()
            if row:
                cv_pref = row['cv_text'][:2000]
                jd_pref = row['jd_text'][:1500]
        return render_template("mock_interview.html", cv_text=cv_pref, jd_text=jd_pref)
    cv_text = request.form.get("cv_text","").strip()
    jd_text = request.form.get("jd_text","").strip()
    jd_url = request.form.get("jd_url","").strip()
    if jd_url and len(jd_text)<30:
        fetched = core.fetch_jd_from_url(jd_url)
        if fetched: jd_text = fetched
    if not cv_text or not jd_text:
        flash("CV and JD required"); return redirect(url_for('mock_interview'))
    questions = core.generate_mock_questions(cv_text, jd_text, n=7)
    # store for evaluation
    session['mock_qs'] = questions
    session['mock_cv'] = cv_text[:3000]
    session['mock_jd'] = jd_text[:3000]
    return render_template("mock_interview_qs.html", questions=questions, cv_text=cv_text[:500], jd_text=jd_text[:500])

@app.route("/mock-interview/evaluate", methods=["POST"])
def mock_evaluate():
    questions = session.get('mock_qs')
    if not questions:
        flash("Start a new mock interview"); return redirect(url_for('mock_interview'))
    results = []
    total = 0
    for i, q in enumerate(questions):
        ans = request.form.get(f"ans_{i}","").strip()
        ev = core.evaluate_answer(q, ans)
        results.append({"q": q, "ans": ans, "ev": ev})
        total += ev["score"]
    avg = round(total/len(questions),1) if questions else 0
    level = "Interview Ready 🌟" if avg>=8 else "Good — Polish Needed" if avg>=6 else "Needs Practice"
    return render_template("mock_interview_result.html", results=results, avg=avg, level=level)

@app.route("/api/mock-interview", methods=["POST"])
def api_mock():
    data = request.get_json(silent=True) or {}
    cv = data.get("cv_text") or ""
    jd = data.get("jd_text") or (data.get("jd_url") and core.fetch_jd_from_url(data.get("jd_url"))) or ""
    if not cv or not jd:
        return jsonify({"error":"cv_text and jd_text required"}), 400
    qs = core.generate_mock_questions(cv, jd)
    return jsonify({"questions": qs})

@app.route("/api/mock-evaluate", methods=["POST"])
def api_mock_eval():
    data = request.get_json(silent=True) or {}
    qs = data.get("questions") or []
    answers = data.get("answers") or []
    if not qs or not answers:
        return jsonify({"error":"questions and answers required"}), 400
    res = []
    for q, a in zip(qs, answers):
        res.append(core.evaluate_answer(q,a))
    avg = round(sum(r["score"] for r in res)/len(res),1) if res else 0
    return jsonify({"evaluations": res, "avg": avg})

@app.route("/api/cover-letter", methods=["POST"])
def api_cover_letter():
    data = request.get_json(silent=True) or {}
    cv = data.get("cv_text") or ""
    jd = data.get("jd_text") or data.get("jd_url") and core.fetch_jd_from_url(data.get("jd_url")) or ""
    if not cv or not jd:
        return jsonify({"error":"cv_text and jd_text (or jd_url) required"}), 400
    letter = core.ai_cover_letter(cv, jd, {"name": data.get("name","")})
    return jsonify({"cover_letter": letter})

@app.route("/analyze", methods=["GET","POST"])
@login_required
def analyze():
    if request.method == "GET":
        return render_template("analyze.html", demo_cv=core.DEMO_CV.strip(), demo_jd=core.DEMO_JD.strip())
    # POST
    cv_text = request.form.get("cv_text","").strip()
    jd_text = request.form.get("jd_text","").strip()
    jd_url = request.form.get("jd_url","").strip()
    if jd_url and len(jd_text)<30:
        fetched = core.fetch_jd_from_url(jd_url)
        if fetched:
            jd_text = fetched
            flash(f"Fetched JD from URL ({len(fetched)} chars)")
        else:
            flash("Could not fetch URL — check link or paste JD")

    # file overrides text if present
    cv_file = request.files.get("cv_file")
    jd_file = request.files.get("jd_file")
    if cv_file and cv_file.filename:
        try:
            cv_text = extract_text_from_upload(cv_file) or cv_text
        except Exception as e:
            flash(f"CV file error: {e}")
    if jd_file and jd_file.filename:
        try:
            jd_text = extract_text_from_upload(jd_file) or jd_text
        except Exception as e:
            flash(f"JD file error: {e}")

    if len(cv_text) < 30:
        flash("CV too short - paste full resume or upload PDF")
        return redirect(url_for("analyze"))
    if len(jd_text) < 10:
        jd_text = core.DEMO_JD  # fallback

    res = core.analyse(cv_text, jd_text)
    # save to DB
    db = get_db()
    db.execute("""INSERT INTO analyses(user_id,overall,verdict,keyword_score,semantic,skill_coverage,
                cv_skills,jd_skills,missing_skills,cv_text,jd_text,result_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        session['user_id'], res['scores']['overall'], res['scores']['verdict'],
        res['scores']['keyword_match'], res['scores']['semantic_similarity'], res['scores']['skill_coverage'],
        json.dumps(res['skills']['cv_skills']), json.dumps(res['skills']['jd_skills']),
        json.dumps(res['skills']['gap']['missing']), cv_text[:8000], jd_text[:8000],
        json.dumps(res, ensure_ascii=False), datetime.now().isoformat()
    ))
    db.commit()
    aid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return render_template("result.html", res=res, aid=aid, cv_text=cv_text[:2000])

@app.route("/history/<int:aid>")
@login_required
def history_view(aid):
    db = get_db()
    row = db.execute("SELECT * FROM analyses WHERE id=? AND user_id=?", (aid, session['user_id'])).fetchone()
    if not row:
        # admin can see all
        if session.get('username')=='admin':
            row = db.execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone()
        if not row:
            flash("Not found"); return redirect(url_for('dashboard'))
    res = json.loads(row['result_json'])
    return render_template("result.html", res=res, aid=aid, cv_text=row['cv_text'][:2000])

@app.route("/enhance/<int:aid>")
@login_required
def enhance_view(aid):
    db = get_db()
    row = db.execute("SELECT * FROM analyses WHERE id=? AND (user_id=? OR ?='admin')", (aid, session['user_id'], session.get('username',''))).fetchone()
    if not row:
        row = db.execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone()
        if not row or row['user_id'] != session['user_id'] and session.get('username')!='admin':
            flash("Not found"); return redirect(url_for('dashboard'))
    res = json.loads(row['result_json'])
    cv_text = row['cv_text']
    jd_text = row['jd_text']
    enhanced = core.ai_enhance_cv(cv_text, jd_text, res)
    return render_template("enhance.html", res=res, enhanced=enhanced, aid=aid, cv_text=cv_text[:2000], jd_text=jd_text[:1200])

@app.route("/api/enhance", methods=["POST"])
def api_enhance():
    data = request.get_json(silent=True) or {}
    cv = data.get("cv_text") or ""
    jd = data.get("jd_text") or ""
    if not cv or not jd:
        return jsonify({"error":"cv_text and jd_text required"}), 400
    res = core.analyse(cv, jd)
    enh = core.ai_enhance_cv(cv, jd, res)
    return jsonify({"analysis": res, "enhanced": enh})

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or {}
    cv = data.get("cv_text") or request.form.get("cv_text","")
    jd = data.get("jd_text") or request.form.get("jd_text","")
    if not cv or not jd:
        return jsonify({"error":"cv_text and jd_text required"}), 400
    res = core.analyse(cv, jd)
    return jsonify(res)

@app.route("/admin")
@login_required
def admin():
    if session.get('username') != 'admin':
        flash("Admin only (login admin/admin123)")
        return redirect(url_for('dashboard'))
    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    analyses = db.execute("SELECT a.*, u.username FROM analyses a LEFT JOIN users u ON a.user_id=u.id ORDER BY a.id DESC LIMIT 50").fetchall()
    return render_template("admin.html", users=users, analyses=analyses)

def _require_login_row(aid):
    db = get_db()
    row = db.execute("SELECT * FROM analyses WHERE id=? AND user_id=?", (aid, session.get('user_id', -1))).fetchone()
    if not row and session.get('username')=='admin':
        row = db.execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone()
    return row

@app.route("/builder", methods=["GET","POST"])
def builder():
    if request.method == "GET":
        return render_template("builder.html")
    jd_url = request.form.get("jd_url","").strip()
    jd_raw = request.form.get("jd","").strip()
    if jd_url and len(jd_raw)<30:
        fetched = core.fetch_jd_from_url(jd_url)
        if fetched:
            jd_raw = fetched
            flash(f"Fetched JD from URL ({len(fetched)} chars)")
        else:
            flash("Could not fetch JD URL — paste manually")
    data = {
        "name": request.form.get("name",""),
        "email": request.form.get("email",""),
        "phone": request.form.get("phone",""),
        "location": request.form.get("location",""),
        "linkedin": request.form.get("linkedin",""),
        "github": request.form.get("github",""),
        "jd": jd_raw,
        "summary": request.form.get("summary",""),
        "education": request.form.get("education",""),
        "skills": request.form.get("skills",""),
        "experience": request.form.get("experience",""),
        "projects": request.form.get("projects",""),
        "certs": request.form.get("certs",""),
    }
    cv_text = core.ai_build_cv(data)
    # also analyze if jd provided, else dummy jd
    jd_text = data["jd"] if data["jd"].strip() else "Software Developer Python React SQL"
    res = core.analyse(cv_text, jd_text)
    # save to history if logged in
    aid = None
    if 'user_id' in session:
        db = get_db()
        db.execute("""INSERT INTO analyses(user_id,overall,verdict,keyword_score,semantic,skill_coverage,
                    cv_skills,jd_skills,missing_skills,cv_text,jd_text,result_json,created_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            session['user_id'], res['scores']['overall'], res['scores']['verdict'],
            res['scores']['keyword_match'], res['scores']['semantic_similarity'], res['scores']['skill_coverage'],
            json.dumps(res['skills']['cv_skills']), json.dumps(res['skills']['jd_skills']),
            json.dumps(res['skills']['gap']['missing']), cv_text[:8000], jd_text[:8000],
            json.dumps(res, ensure_ascii=False), datetime.now().isoformat()
        ))
        db.commit()
        aid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        # store built cv for pdf route
        # also save as analysis already, use same id for builder download
    else:
        # guest: generate temp id via timestamp
        aid = int(datetime.now().timestamp())
        # store in session for download (simple)
        session['built_cv'] = cv_text
        session['built_res'] = json.dumps(res)
    return render_template("builder_result.html", cv_text=cv_text, res=res, aid=aid, name=data["name"])

@app.route("/download/built/<int:aid>")
def download_built(aid):
    # try DB first
    row = None
    if 'user_id' in session:
        db = get_db()
        row = db.execute("SELECT * FROM analyses WHERE id=? AND user_id=?", (aid, session.get('user_id', -1))).fetchone()
        if not row and session.get('username')=='admin':
            row = db.execute("SELECT * FROM analyses WHERE id=?", (aid,)).fetchone()
    if row:
        cv_text = row['cv_text']
        res = json.loads(row['result_json'])
    elif 'built_cv' in session:
        cv_text = session['built_cv']
        res = json.loads(session.get('built_res','{}'))
    else:
        flash("Resume not found — rebuild"); return redirect(url_for('builder'))
    lines = [
        ("Resume — ATS Safe (Generated by ResumePro AI Builder)", cv_text),
        ("Analysis (if JD provided)", f"Score {res.get('scores',{}).get('overall','--')}/100 — {res.get('scores',{}).get('verdict','')}") if res else ("Note","Build without JD — paste JD in Analyze for score"),
    ]
    buf, mime = _make_pdf("AI Built Resume — ResumePro AI", lines, f"Built_{aid}.pdf")
    ext = "pdf" if mime=="application/pdf" else "txt"
    return send_file(buf, as_attachment=True, download_name=f"AI_Resume_{aid}.{ext}", mimetype=mime)

def _make_pdf(title, lines, filename):
    """Generate PDF with reportlab, fallback to text if not available"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.units import inch
        import reportlab.lib.colors as colors
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle('h1', parent=styles['Heading1'], fontSize=18, textColor=HexColor('#0f172a'), spaceAfter=6)
        h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontSize=13, textColor=HexColor('#4f46e5'), spaceAfter=4)
        normal = ParagraphStyle('normal', parent=styles['Normal'], fontSize=9, leading=12)
        story = []
        story.append(Paragraph(title, h1))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} • ResumePro AI — BCA Project 2026", normal))
        story.append(Spacer(1, 12))
        for section, content in lines:
            story.append(Paragraph(section, h2))
            # content can be str or list
            if isinstance(content, list):
                for line in content:
                    # escape html
                    safe = line.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                    story.append(Paragraph(safe, normal))
            else:
                safe = content.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>')
                story.append(Paragraph(safe, normal))
            story.append(Spacer(1, 8))
        doc.build(story)
        buf.seek(0)
        return buf, "application/pdf"
    except Exception as e:
        # fallback: plain text as pdf mimetype
        txt = title + "\n" + "="*60 + "\n"
        for sec, cont in lines:
            txt += f"\n{sec}\n" + "-"*40 + "\n"
            if isinstance(cont, list):
                txt += "\n".join(cont) + "\n"
            else:
                txt += cont + "\n"
        buf = io.BytesIO(txt.encode('utf-8'))
        return buf, "text/plain"

@app.route("/download/report/<int:aid>")
@login_required
def download_report(aid):
    row = _require_login_row(aid)
    if not row:
        flash("Not found"); return redirect(url_for('dashboard'))
    res = json.loads(row['result_json'])
    s = res['scores']
    lines = [
        ("Overall Score", f"{s['overall']}/100 — {s['verdict']}\nKeyword: {s['keyword_match']}%  Semantic: {s['semantic_similarity']}%  Skills: {s['skill_coverage']}%  Method: {res['meta']['method']}"),
        ("Contact & ATS", res['ats_checks']),
        ("Skills Gap", [
            f"CV skills: {', '.join(res['skills']['cv_skills'])}",
            f"JD skills: {', '.join(res['skills']['jd_skills'])}",
            f"Matched: {', '.join(res['skills']['gap']['matched'])}",
            f"Missing: {', '.join(res['skills']['gap']['missing'])}",
            f"Extra: {', '.join(res['skills']['gap']['extra'][:8])}",
        ]),
        ("Keywords", [
            f"Top JD: {', '.join(f'{k}({v})' for k,v in res['keywords']['top_jd_keywords'][:12])}",
            f"Matched {len(res['keywords']['matched'])}: {', '.join(res['keywords']['matched'][:30])}",
            f"Missing: {', '.join(res['keywords']['missing'][:25])}",
        ]),
        ("Raw CV (first 800 chars)", row['cv_text'][:800]),
    ]
    buf, mime = _make_pdf(f"ResumePro AI — Analysis Report #{aid}", lines, f"Report_{aid}.pdf")
    ext = "pdf" if mime=="application/pdf" else "txt"
    return send_file(buf, as_attachment=True, download_name=f"ResumePro_Report_{aid}.{ext}", mimetype=mime)

@app.route("/download/cv/<int:aid>")
@login_required
def download_cv(aid):
    row = _require_login_row(aid)
    if not row:
        flash("Not found"); return redirect(url_for('dashboard'))
    res = json.loads(row['result_json'])
    enhanced = core.ai_enhance_cv(row['cv_text'], row['jd_text'], res)
    lines = [
        ("Enhanced Resume (ATS-Safe)", enhanced['enhanced_full']),
        ("What was fixed", enhanced['fixes']),
        ("Predicted Score", f"Before: {res['scores']['overall']}%  →  After: {enhanced['predicted_score']}%  (+{enhanced['boost']}%)"),
    ]
    buf, mime = _make_pdf(f"Enhanced Resume — ResumePro AI #{aid}", lines, f"Enhanced_{aid}.pdf")
    ext = "pdf" if mime=="application/pdf" else "txt"
    return send_file(buf, as_attachment=True, download_name=f"Enhanced_Resume_{aid}.{ext}", mimetype=mime)

@app.route("/download/txt/<int:aid>")
@login_required
def download_txt(aid):
    row = _require_login_row(aid)
    if not row:
        flash("Not found"); return redirect(url_for('dashboard'))
    buf = io.BytesIO(row['cv_text'].encode('utf-8'))
    return send_file(buf, as_attachment=True, download_name=f"Resume_{aid}.txt", mimetype="text/plain")

# CLI demo
@app.route("/demo")
def demo():
    res = core.analyse(core.DEMO_CV, core.DEMO_JD)
    return jsonify(res)

if __name__ == "__main__":
    init_db()
    print("="*60)
    print(" BCA Project: Smart AI Resume Analyzer")
    print(" URL: http://127.0.0.1:5000")
    print(" Login: admin / admin123  (or Register new user)")
    print("="*60)
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
