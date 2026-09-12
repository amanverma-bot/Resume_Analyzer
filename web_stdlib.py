#!/usr/bin/env python3
"""
CV Analyser - Web UI (zero dependencies, stdlib only)
Run: python3 cv_analyser_web.py
Then open: http://127.0.0.1:8000  or http://localhost:8000
"""
import http.server
import socketserver
import urllib.parse
import json
import re

# reuse logic from cv_analyser.py
import cv_analyser as core

PORT = 8000

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CV Analyser</title>
<style>
*{box-sizing:border-box;font-family:system-ui,Segoe UI,Roboto,sans-serif}
body{max-width:900px;margin:0 auto;padding:20px;background:#f6f7f9;color:#111}
h1{margin:0 0 8px} .sub{color:#666;margin-bottom:20px}
.card{background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 10px rgba(0,0,0,.07);margin-bottom:16px}
textarea{width:100%;min-height:180px;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:14px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:700px){.row{grid-template-columns:1fr}}
.btn{background:#111;color:#fff;border:0;padding:12px 18px;border-radius:8px;font-weight:600;cursor:pointer;width:100%;font-size:15px}
.btn:hover{opacity:.9}
.badge{display:inline-block;padding:4px 10px;border-radius:999px;font-size:13px;font-weight:600}
.score{font-size:42px;font-weight:800;margin:6px 0}
pre{white-space:pre-wrap;word-break:break-word;background:#0f172a;color:#e2e8f0;padding:16px;border-radius:10px;font-size:13px;line-height:1.5;overflow:auto}
.file{font-size:13px;color:#666}
.kv{display:grid;grid-template-columns:140px 1fr;gap:6px;font-size:14px}
</style>
</head>
<body>
<h1>📄 CV Analyser</h1>
<div class="sub">Paste CV + Job Description → get ATS score, keyword & skill gap. Works offline. Demo pre-filled.</div>

<form method="POST" enctype="multipart/form-data">
<div class="row">
<div class="card">
<h3>CV (resume) — paste or upload .txt/.pdf/.docx</h3>
<textarea name="cv_text" placeholder="Paste CV text here...">""" + core.DEMO_CV.strip() + r"""</textarea>
<p class="file"><input type="file" name="cv_file" accept=".txt,.pdf,.docx,.md"></p>
</div>
<div class="card">
<h3>Job Description</h3>
<textarea name="jd_text" placeholder="Paste JD here...">""" + core.DEMO_JD.strip() + r"""</textarea>
<p class="file"><input type="file" name="jd_file" accept=".txt,.pdf,.docx,.md"></p>
</div>
</div>
<button class="btn" type="submit">🔍 Analyse CV</button>
</form>

<div style="text-align:center;margin:16px;color:#888;font-size:13px">Tip: also try CLI → <code>python3 cv_analyser.py --demo</code></div>

<!--RESULT-->
</body>
</html>
"""

def render_result(res):
    s = res["scores"]
    # color by score
    color = "#16a34a" if s["overall"]>=80 else "#ca8a04" if s["overall"]>=65 else "#ea580c" if s["overall"]>=45 else "#dc2626"
    gap = res["skills"]["gap"]
    kw = res["keywords"]
    # build html snippet
    html = f"""
<div class="card" style="border-left:6px solid {color}">
<div class="badge" style="background:{color};color:#fff">{s['verdict']}</div>
<div class="score" style="color:{color}">{s['overall']}/100</div>
<div class="kv">
<div>Keyword Match</div><div><b>{s['keyword_match']}%</b> ({kw['matched_count']}/{kw['total_keywords']})</div>
<div>Semantic</div><div><b>{s['semantic_similarity']}%</b> <span style="color:#888">[{res['meta']['method']}]</span></div>
<div>Skill Coverage</div><div><b>{s['skill_coverage']}%</b></div>
<div>CV words</div><div>{res['meta']['cv_words']} • JD words {res['meta']['jd_words']}</div>
</div>
</div>

<div class="card">
<h3>📇 Contact & ATS</h3>
<div class="kv">
<div>Emails</div><div>{', '.join(res['contact']['emails']) or '❌ NOT FOUND'}</div>
<div>Phones</div><div>{', '.join(res['contact']['phones']) or '❌ NOT FOUND'}</div>
<div>Sections</div><div>present: {', '.join([k for k,v in res['sections'].items() if v])}<br>missing: {', '.join([k for k,v in res['sections'].items() if not v]) or 'none'}</div>
</div>
<pre>{chr(10).join(res['ats_checks'])}</pre>
</div>

<div class="card">
<h3>🛠️ Skills Gap</h3>
<p><b>CV:</b> {', '.join(res['skills']['cv_skills']) or 'none'}</p>
<p><b>JD:</b> {', '.join(res['skills']['jd_skills']) or 'none'}</p>
<p style="color:#16a34a"><b>✅ Matched:</b> {', '.join(gap['matched']) or '—'}</p>
<p style="color:#dc2626"><b>❌ Missing (add):</b> {', '.join(gap['missing']) or '—'}</p>
<p style="color:#666"><b>ℹ️ Extra:</b> {', '.join(gap['extra'][:10]) or '—'}</p>
</div>

<div class="card">
<h3>🔑 Keywords</h3>
<p style="font-size:13px;color:#666">Top JD: {', '.join(f"{k}({v})" for k,v in kw['top_jd_keywords'][:12])}</p>
<p style="color:#16a34a"><b>✅ Matched {len(kw['matched'])}:</b> {', '.join(kw['matched'][:40])}</p>
<p style="color:#dc2626"><b>❌ Missing top 25:</b> {', '.join(kw['missing'][:25])}</p>
</div>

<div class="card">
<h3>💡 Actionable Fixes</h3>
<pre>{core.pretty_report(res, '', '')}</pre>
</div>

<div class="card">
<details><summary>Show raw JSON</summary><pre>{json.dumps(res, indent=2, ensure_ascii=False)}</pre></details>
</div>
"""
    return html

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def parse_multipart(self, data: bytes, boundary: bytes):
        """Minimal multipart parser without cgi module (Python 3.13+ removed cgi)"""
        parts = {}
        # split by boundary
        delimiter = b'--' + boundary
        for part in data.split(delimiter):
            if not part or part == b'--\r\n' or part.strip() == b'--':
                continue
            if b'\r\n\r\n' not in part:
                continue
            header, body = part.split(b'\r\n\r\n', 1)
            # strip trailing \r\n
            if body.endswith(b'\r\n'):
                body = body[:-2]
            header_str = header.decode('utf-8', errors='ignore')
            m = re.search(r'name="([^"]+)"(?:;\s*filename="([^"]*)")?', header_str)
            if not m:
                continue
            name = m.group(1)
            filename = m.group(2) if m.group(2) else None
            parts[name] = (filename, body)
        return parts

    def do_POST(self):
        ctype = self.headers.get('content-type', '')
        cv_text = ""
        jd_text = ""
        # read body
        length = int(self.headers.get('content-length', 0))
        raw = self.rfile.read(length) if length else b""
        if ctype.startswith('multipart/form-data'):
            # extract boundary
            m = re.search(r'boundary=([^;]+)', ctype)
            boundary = m.group(1).strip().strip('"').encode() if m else None
            if boundary:
                parts = self.parse_multipart(raw, boundary)
                # text fields
                if 'cv_text' in parts:
                    _, body = parts['cv_text']
                    cv_text = body.decode('utf-8', errors='ignore')
                if 'jd_text' in parts:
                    _, body = parts['jd_text']
                    jd_text = body.decode('utf-8', errors='ignore')
                # file fields override text if provided
                for field, target in [('cv_file', 'cv_text'), ('jd_file', 'jd_text')]:
                    if field in parts:
                        fname, body = parts[field]
                        if fname:  # file was selected
                            try:
                                if fname.lower().endswith('.pdf'):
                                    import tempfile
                                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tf:
                                        tf.write(body); tf.flush()
                                        text = core.read_pdf(tf.name)
                                    if target == 'cv_text': cv_text = text
                                    else: jd_text = text
                                elif fname.lower().endswith('.docx'):
                                    import tempfile
                                    with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tf:
                                        tf.write(body); tf.flush()
                                        text = core.read_docx_file(tf.name)
                                    if target == 'cv_text': cv_text = text
                                    else: jd_text = text
                                else:
                                    text = body.decode('utf-8', errors='ignore')
                                    if target == 'cv_text' and text.strip(): cv_text = text
                                    elif target == 'jd_text' and text.strip(): jd_text = text
                            except Exception:
                                pass
            # fallback if parsing failed
            if not cv_text and not jd_text:
                # try urlencoded fallback
                body = raw.decode('utf-8', errors='ignore')
                params = urllib.parse.parse_qs(body)
                cv_text = params.get('cv_text', [''])[0]
                jd_text = params.get('jd_text', [''])[0]
        else:
            body = raw.decode('utf-8', errors='ignore')
            params = urllib.parse.parse_qs(body)
            cv_text = params.get('cv_text', [''])[0]
            jd_text = params.get('jd_text', [''])[0]

        if isinstance(cv_text, bytes): cv_text = cv_text.decode('utf-8', errors='ignore')
        if isinstance(jd_text, bytes): jd_text = jd_text.decode('utf-8', errors='ignore')

        # default to demo if empty
        if len(cv_text.strip()) < 20:
            cv_text = core.DEMO_CV
        if len(jd_text.strip()) < 10:
            jd_text = core.DEMO_JD

        try:
            res = core.analyse(cv_text, jd_text)
            result_html = render_result(res)
        except Exception as e:
            import traceback
            result_html = f'<div class="card" style="border-left:6px solid #dc2626"><h3>❌ Error</h3><pre>{e}\n\n{traceback.format_exc()}</pre></div>'

        out = HTML.replace("<!--RESULT-->", result_html)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(out.encode())

    def log_message(self, format, *args):
        # quieter log
        print(f"{self.client_address[0]} - {format%args}")

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"✅ CV Analyser Web UI running at:")
        print(f"   http://127.0.0.1:{PORT}")
        print(f"   http://localhost:{PORT}")
        print(f"   (Termux: open in browser, or use 'termux-open-url http://127.0.0.1:{PORT}')")
        print(f"Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
