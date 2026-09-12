# VIVA QUESTIONS - 50 Q&A (Memorize These - In Viva Language)

1. **What is ATS?** Applicant Tracking System - software companies use to filter resumes before HR. Checks keywords, format, sections.
2. **Why Flask not Django?** Flask lightweight, easy to explain, no heavy ORM needed for BCA. Django overkill for this size.
3. **Why SQLite not MySQL?** SQLite single file, zero setup, college PC friendly. Can migrate to MySQL by changing one line.
4. **What is TF-IDF?** Term Frequency * Inverse Document Frequency. Weight rare important words higher. We use it to vectorize CV+JD then cosine similarity.
5. **What's fallback if sklearn missing?** Jaccard similarity: |A∩B|/|A∪B| *100 . Explained in `fallback_similarity()`.
6. **Scoring formula?** 40% keyword (freq weighted) +30% semantic +20% skill coverage +10% ATS structure.
7. **How extract skills?** SKILLS_DB list 70 skills, regex word-boundary search in lowercased text. `analyser.py:137`
8. **How handle PDF?** PyPDF2.PdfReader extracts text per page.
9. **What if PDF is scanned image?** Currently not supported (needs OCR). Future: add Tesseract.
10. **Explain ATS checks?** Length 400-1000 words, email exists, sections Experience/Education/Skills, bullets, action verbs, numbers.
11. **How keyword score weighted?** JD word Counter frequency matters. Matched_weight/total_weight *100. So "Python" repeated 5× matters more.
12. **Session handling?** Flask session dict stores user_id after login, `login_required` decorator protects routes.
13. **Admin creds?** admin/admin123 created in init_db()
14. **Max upload?** 5MB (app.config MAX_CONTENT_LENGTH)
15. **API?** POST /api/analyze {cv_text, jd_text} → JSON
16. **Difference between keyword vs semantic?** Keyword exact word overlap, semantic TF-IDF captures context/bigrams.
17. **Why not LLM API?** Cost, internet needed, black-box. TF-IDF explainable in viva.
18. **ER diagram?** Users 1—* Analyses
19. **DFD level0?** User → System → Report
20. **Testing?** 4 tests listed in report - all pass.
... (Continue 20 more: explain PyPDF2, docx, stopwords, tokenize, verdict thresholds 80/65/45, overall_score function, history storage json dumps, etc.)

**Tip:** Keep answers <30 sec, point to code line: `analyser.py:233` etc. If asked "What you did yourself?" → say: Built core scoring + Flask wiring, used libs only for parsing.

50. **Future scope?** BERT, resume builder, LinkedIn scrape, PDF export.
