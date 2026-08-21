import os
from dotenv import load_dotenv
load_dotenv()
import json
import sqlite3
import logging
import re
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from groq import Groq
import fitz  # PyMuPDF

# ==========================================================================
# LOGGING CONFIGURATION
# ==========================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ==========================================================================
# FLASK CONFIGURATION
# ==========================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "eduai-pro-secret-key-99881122")

UPLOAD_FOLDER = "uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx", "doc", "png", "jpg", "jpeg", "md"}
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# ==========================================
# GROQ API KEY INITIALIZATION
# ==========================================
def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY environment variable is not set. "
            "Please configure the key in your terminal before running the application."
        )
    return Groq(api_key=api_key)

# ==========================================================================
# DATABASE SCHEMAS & UTILITIES
# ==========================================================================
class DatabaseCursorWrapper:
    def __init__(self, cursor, is_postgres=False):
        self.cursor = cursor
        self.is_postgres = is_postgres

    def execute(self, query, params=None):
        if self.is_postgres and params is not None:
            query = query.replace('?', '%s')
        
        if params is not None:
            self.cursor.execute(query, params)
        else:
            self.cursor.execute(query)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def __iter__(self):
        return self

    def __next__(self):
        res = self.cursor.fetchone()
        if res is None:
            raise StopIteration
        return res

    @property
    def lastrowid(self):
        if self.is_postgres:
            self.cursor.execute("SELECT lastval()")
            return self.cursor.fetchone()[0]
        else:
            return self.cursor.lastrowid

class DatabaseConnectionWrapper:
    def __init__(self, conn, is_postgres=False):
        self.conn = conn
        self.is_postgres = is_postgres

    def cursor(self):
        return DatabaseCursorWrapper(self.conn.cursor(), self.is_postgres)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

DATABASE = "database.db"

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    if db_url:
        import psycopg2
        import psycopg2.extras
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)
        return DatabaseConnectionWrapper(conn, is_postgres=True)
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return DatabaseConnectionWrapper(conn, is_postgres=False)

def init_db():
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
    is_postgres = bool(db_url)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if is_postgres:
            # PostgreSQL syntax
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS materials (
                    id              SERIAL PRIMARY KEY,
                    filename        VARCHAR(255) NOT NULL,
                    filepath        VARCHAR(255) NOT NULL,
                    extracted_text  TEXT NOT NULL,
                    summary_detailed TEXT,
                    summary_short   TEXT,
                    summary_revision TEXT,
                    summary_onepage  TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flashcards (
                    id          SERIAL PRIMARY KEY,
                    material_id INTEGER NOT NULL,
                    front       TEXT NOT NULL,
                    back        TEXT NOT NULL,
                    FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id              SERIAL PRIMARY KEY,
                    username        VARCHAR(255) NOT NULL,
                    filename        VARCHAR(255) NOT NULL,
                    topic           VARCHAR(255) NOT NULL,
                    difficulty      VARCHAR(50) NOT NULL,
                    score           INTEGER NOT NULL,
                    total           INTEGER NOT NULL,
                    percentage      REAL NOT NULL,
                    weak_topics     TEXT,
                    study_plan_1d   TEXT,
                    study_plan_3d   TEXT,
                    study_plan_7d   TEXT,
                    readiness_score INTEGER,
                    confidence      VARCHAR(50),
                    tutor_feedback  TEXT,
                    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # SQLite syntax
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS materials (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename        TEXT NOT NULL,
                    filepath        TEXT NOT NULL,
                    extracted_text  TEXT NOT NULL,
                    summary_detailed TEXT,
                    summary_short   TEXT,
                    summary_revision TEXT,
                    summary_onepage  TEXT,
                    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS flashcards (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER NOT NULL,
                    front       TEXT NOT NULL,
                    back        TEXT NOT NULL,
                    FOREIGN KEY(material_id) REFERENCES materials(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    username        TEXT NOT NULL,
                    filename        TEXT NOT NULL,
                    topic           TEXT NOT NULL,
                    difficulty      TEXT NOT NULL,
                    score           INTEGER NOT NULL,
                    total           INTEGER NOT NULL,
                    percentage      REAL NOT NULL,
                    weak_topics     TEXT,
                    study_plan_1d   TEXT,
                    study_plan_3d   TEXT,
                    study_plan_7d   TEXT,
                    readiness_score INTEGER,
                    confidence      TEXT,
                    tutor_feedback  TEXT,
                    timestamp       DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
        # Migrate any 'Student', 'Steve', 'Maria John', or 'Sneha' records to 'Sujay'
        cursor.execute("UPDATE quiz_results SET username = 'Sujay' WHERE username IN ('Student', 'Steve', 'Maria John', 'Sneha', 'Sneha S')")
        
        conn.commit()
        conn.close()
        logger.info("Database Tables initialized and records migrated successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

# ==========================================================================
# HELPER FUNCTIONS
# ==========================================================================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[-1].lower() in ALLOWED_EXTENSIONS

def extract_clean_text_from_file(filepath):
    """Extract and sanitize text from various file formats (PDF, DOCX, TXT, MD, images)."""
    ext = filepath.rsplit(".", 1)[-1].lower()
    text = ""
    
    if ext == "pdf":
        # Try pypdf first (pure Python, 100% reliable on Vercel)
        try:
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            if len(reader.pages) == 0:
                raise ValueError("The PDF appears to be empty (0 pages).")
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        except Exception as pypdf_err:
            logger.warning(f"pypdf extraction failed: {pypdf_err}. Trying PyMuPDF...")
            try:
                pdf = fitz.open(filepath)
                if pdf.page_count == 0:
                    raise ValueError("The PDF appears to be empty (0 pages).")
                for page_num in range(pdf.page_count):
                    page = pdf[page_num]
                    text += page.get_text() + "\n"
                pdf.close()
            except fitz.FileDataError:
                raise ValueError("The file uploaded is not a valid or readable PDF.")
            except Exception as e:
                raise ValueError(f"Failed to parse PDF: {str(e)}")
                
    elif ext in ("docx", "doc"):
        try:
            import docx
            doc = docx.Document(filepath)
            fullText = []
            for para in doc.paragraphs:
                fullText.append(para.text)
            text = "\n".join(fullText)
        except Exception as e:
            raise ValueError(f"Failed to parse Word Document: {str(e)}")
            
    elif ext in ("txt", "md"):
        for encoding in ("utf-8", "latin-1", "utf-16"):
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    text = f.read()
                    break
            except Exception:
                continue
        if not text:
            raise ValueError("Could not read text file or file is empty.")
            
    elif ext in ("png", "jpg", "jpeg"):
        try:
            import base64
            with open(filepath, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            mime_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"
            client = get_groq_client()
            
            logger.info(f"Extracting text from image {filepath} using Groq vision model...")
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are a highly accurate document transcription system. "
                                    "Read the text in this image and output ONLY the transcribed text. "
                                    "Do not add any greeting, formatting, markdown blocks (like ```), or comments. "
                                    "Just output the exact words found in the document."
                                )
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2048,
            )
            text = response.choices[0].message.content.strip()
        except Exception as e:
            raise ValueError("Image OCR transcription is unavailable. Please upload a PDF, Word (.docx), Markdown (.md), or text (.txt) document.")
            
    else:
        raise ValueError(f"Unsupported file format: .{ext}")

    # Basic text cleaning: remove extra spacing
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        if ext == "pdf":
            raise ValueError("No readable text found in this PDF. If it is a scanned/image PDF, please upload a searchable PDF, Word (.docx), or text (.txt) file.")
        raise ValueError("No readable text was found in the file. Please check if the file is empty or corrupted.")
    return text

# ==========================================================================
# GROQ AI AGENT CALLS
# ==========================================================================
def call_groq_with_fallback(prompt, system_prompt=None, primary_model="openai/gpt-oss-120b", fallback_model="openai/gpt-oss-20b", temperature=0.5, max_tokens=3000):
    """Call Groq chat completions API with primary model and automatic cascading fallback on error."""
    client = get_groq_client()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    model_chain = [primary_model, fallback_model, "qwen/qwen3.6-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    seen = set()
    models_to_try = [m for m in model_chain if m and not (m in seen or seen.add(m))]

    last_error = None
    for model_name in models_to_try:
        try:
            logger.info(f"Attempting API call using model '{model_name}'...")
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Model '{model_name}' failed with error: {e}. Trying next fallback...")
            last_error = e
            continue

    raise RuntimeError(f"All Groq AI models failed. Last error: {last_error}")

def parse_json_from_llm(raw_content, is_list=True):
    """Robustly parse JSON list or object output from LLM, stripping surrounding markdown or conversations."""
    raw_content = raw_content.strip()
    
    # 1. Try split by code fence blocks
    if "```" in raw_content:
        parts = raw_content.split("```")
        for part in parts:
            part_clean = part.strip()
            if part_clean.startswith("json"):
                part_clean = part_clean[4:].strip()
            if is_list and part_clean.startswith("[") and part_clean.endswith("]"):
                try:
                    return json.loads(part_clean)
                except Exception:
                    pass
            elif not is_list and part_clean.startswith("{") and part_clean.endswith("}"):
                try:
                    return json.loads(part_clean)
                except Exception:
                    pass

    # 2. Try locating start/end bracket/brace
    start_char = "[" if is_list else "{"
    end_char = "]" if is_list else "}"
    start_idx = raw_content.find(start_char)
    end_idx = raw_content.rfind(end_char)
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        candidate = raw_content[start_idx:end_idx + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    # 3. Direct decode fallback
    return json.loads(raw_content)

def generate_summaries(text):
    """Generate 4 summary formats from study text in a single structured prompt."""
    trimmed_text = text[:8000]

    prompt = f"""You are an EdTech reading specialist. Based on the study material below, generate four distinct summary styles:
1. Detailed Summary: A comprehensive conceptual breakdown.
2. Short Summary: 2-3 sentences max summarizing core themes.
3. Exam Revision Summary: Bullet points of major definitions/formulas.
4. One-Page Quick Notes: Structured outline/cheat sheet.

Strictly format your response with these exact tag separators so it can be parsed cleanly:
[DETAILED_SUMMARY]
(Detailed content here)
[SHORT_SUMMARY]
(Short summary here)
[EXAM_REVISION]
(Exam revision content here)
[ONE_PAGE_NOTES]
(One page notes here)

Study Material:
{trimmed_text}
"""
    try:
        content = call_groq_with_fallback(prompt, temperature=0.4, max_tokens=3000)

        # Parsing using regex
        detailed = re.search(r'\[DETAILED_SUMMARY\](.*?)\[SHORT_SUMMARY\]', content, re.DOTALL)
        short = re.search(r'\[SHORT_SUMMARY\](.*?)\[EXAM_REVISION\]', content, re.DOTALL)
        revision = re.search(r'\[EXAM_REVISION\](.*?)\[ONE_PAGE_NOTES\]', content, re.DOTALL)
        onepage = re.search(r'\[ONE_PAGE_NOTES\](.*)', content, re.DOTALL)

        return (
            (detailed.group(1).strip() if detailed else "Detailed summary could not be parsed."),
            (short.group(1).strip() if short else "Short summary could not be parsed."),
            (revision.group(1).strip() if revision else "Revision summary could not be parsed."),
            (onepage.group(1).strip() if onepage else "One-page notes could not be parsed.")
        )
    except Exception as e:
        logger.error(f"Failed to generate summaries: {e}")
        return ("Error generating summary.", "Error generating summary.", "Error generating summary.", "Error generating summary.")

def generate_flashcards(text):
    """Generate a clean list of 20 conceptual flashcards."""
    trimmed_text = text[:7000]

    prompt = f"""Based on the study notes below, generate exactly 20 conceptual flashcards in a valid JSON list.
Each flashcard must contain:
- 'front': A question or concept name.
- 'back': A concise answer, definition, or formula.

Return ONLY the raw JSON list format. No explanations, no markdown, no code fences.

Study Notes:
{trimmed_text}
"""
    try:
        raw_content = call_groq_with_fallback(prompt, temperature=0.5, max_tokens=2500)
        cards = parse_json_from_llm(raw_content, is_list=True)
        return cards if isinstance(cards, list) else []
    except Exception as e:
        logger.error(f"Failed to generate flashcards: {e}")
        return []

def generate_quiz(text, difficulty, count):
    """Generate a quiz with custom difficulty and question count."""
    trimmed_text = text[:8000]

    prompt = f"""Based on the study material below, generate exactly {count} multiple-choice questions (MCQs) in a valid JSON list format.
Difficulty level: {difficulty} (Easy = basic definitions, Medium = conceptual application, Hard = analytical problem solving).

Rules:
- Return ONLY a valid JSON list of objects.
- No explanation text, no code block backticks (```).
- Each MCQ must have:
  - "question": "Question string?"
  - "options": ["A", "B", "C", "D"] (Provide exactly 4 distinct choices)
  - "answer": "The exact string representing the correct option choice"

Study Material:
{trimmed_text}
"""
    try:
        raw_content = call_groq_with_fallback(prompt, temperature=0.5, max_tokens=3000)
        quiz_list = parse_json_from_llm(raw_content, is_list=True)
        return quiz_list if isinstance(quiz_list, list) else []
    except Exception as e:
        logger.error(f"Failed to generate quiz: {e}")
        return []

def generate_tutor_analytics_and_study_plans(quiz_data, user_answers):
    """Perform performance evaluation, tutoring feedback, weak area detection, and study plan generator in a single call."""
    # Bundle input for Groq analysis
    submission_bundle = []
    for idx, q in enumerate(quiz_data):
        user_ans = user_answers.get(f"q{idx}", "Not Answered")
        submission_bundle.append({
            "index": idx,
            "question": q["question"],
            "options": q["options"],
            "correct_answer": q["answer"],
            "user_answer": user_ans,
            "status": "Correct" if user_ans == q["answer"] else "Incorrect"
        })

    prompt = f"""Analyze the student's performance on the following quiz:
{json.dumps(submission_bundle, indent=2)}

You must generate:
1. Weak Topics: Identify specific weak modules/concepts and allocate a weakness percentage (e.g. 40%) along with bullet revision tasks.
2. Personalized Study Plans: Write concrete time/task-based routines for 1-Day, 3-Day, and 7-Day durations.
3. Exam Readiness Score: Calculate an overall readiness percentage (0-100), define a confidence level, and write key study focus guidelines.
4. Tutor Feedback: For each INCORRECT answer, generate a tutoring explanation explaining:
   - Why the student's answer is wrong.
   - The correct conceptual definition.
   - A clear example showing the concept in action.

Return ONLY a valid JSON object matching this exact structure:
{{
  "weak_topics": [
    {{
      "topic": "Semiconductor Physics",
      "percentage": 35,
      "revision_items": ["Diodes", "Clippers", "Clampers"]
    }}
  ],
  "study_plan_1d": [
    "9:00 AM - 10:00 AM: Re-read basic diodes",
    "10:00 AM - 11:30 AM: Try practice test on clippers"
  ],
  "study_plan_3d": [
    "Day 1: Conceptual review of weak topics",
    "Day 2: Flashcards review and quiz practice",
    "Day 3: Final self-assessment and exam readiness check"
  ],
  "study_plan_7d": [
    "Day 1-2: Foundations and definitions review",
    "Day 3-4: Diagram drawings and numerical worksheets",
    "Day 5-6: Intermediate interactive assessments",
    "Day 7: Performance review and exam simulations"
  ],
  "readiness_score": 75,
  "confidence": "Medium",
  "recommendations": "Concentrate on semiconductors and logic circuits before trying hard questions.",
  "tutor_feedback": {{
    "0": {{
      "why_wrong": "The user answer incorrectly identified Silicon as a pure conductor instead of a semiconductor.",
      "correct_explanation": "Silicon is a semiconductor, meaning its electrical conductivity lies between that of a conductor and an insulator.",
      "important_concept": "Semiconductors have a moderate bandgap that lets them change state when electrical voltage is applied.",
      "example": "Silicon is used inside CPUs to build transistors acting as switches."
    }}
  }}
}}

Make sure the keys in 'tutor_feedback' correspond to the question index (e.g., "0", "2") of incorrect answers. If all questions are correct, return an empty object for 'tutor_feedback'.
"""
    try:
        raw_content = call_groq_with_fallback(prompt, temperature=0.4, max_tokens=3500)
        return parse_json_from_llm(raw_content, is_list=False)
    except Exception as e:
        logger.error(f"Failed to generate tutor analytics: {e}")
        # Return fallback structure
        return {
            "weak_topics": [{"topic": "General Topics", "percentage": 50, "revision_items": ["Review notes"]}],
            "study_plan_1d": ["9:00 AM: Review notes", "10:00 AM: Quiz revision"],
            "study_plan_3d": ["Day 1: Read notes", "Day 2: Flashcards", "Day 3: Self-test"],
            "study_plan_7d": ["Day 1-3: Review theory", "Day 4-5: Re-take quizzes", "Day 6-7: Final prep"],
            "readiness_score": 60,
            "confidence": "Medium",
            "recommendations": "Review incorrect answers and read explanations.",
            "tutor_feedback": {}
        }

# ==========================================================================
# FLASK WEB APP ROUTES
# ==========================================================================

@app.route("/")
def home():
    """Portal Dashboard listing uploaded files, quiz analytics charts, and historical summary logs."""
    # Ensure a default username exists in session to simulate user logins
    if "username" not in session or session["username"] in ("Student", "Steve", "Maria John", "Sneha", "Sneha S"):
        session["username"] = "Sujay"

    conn = get_db_connection()
    materials = conn.execute("SELECT id, filename, created_at FROM materials ORDER BY id DESC").fetchall()
    
    # Calculate performance metrics
    stats = conn.execute("""
        SELECT 
            COUNT(*) as total_quizzes,
            AVG(score) as avg_score,
            AVG(total) as avg_total,
            MAX(score) as max_score,
            MIN(score) as min_score,
            AVG(percentage) as avg_percentage
        FROM quiz_results 
        WHERE username = ?
    """, (session["username"],)).fetchone()
    
    history_records = conn.execute("""
        SELECT id, filename, topic, difficulty, score, total, percentage, readiness_score, timestamp
        FROM quiz_results 
        WHERE username = ?
        ORDER BY id DESC
    """, (session["username"],)).fetchall()
    
    conn.close()

    # Pre-process stats safely
    total_quizzes = stats["total_quizzes"] or 0
    avg_score = round(stats["avg_percentage"], 1) if stats["avg_percentage"] else 0
    highest_score = round(stats["max_score"], 1) if stats["max_score"] is not None else 0
    lowest_score = round(stats["min_score"], 1) if stats["min_score"] is not None else 0

    # Mock user improvement rate calculation
    improvement_rate = 0
    if len(history_records) > 1:
        latest_pct = history_records[0]["percentage"]
        first_pct = history_records[-1]["percentage"]
        improvement_rate = round(latest_pct - first_pct, 1)

    return render_template(
        "index.html",
        materials=materials,
        total_quizzes=total_quizzes,
        avg_score=avg_score,
        highest_score=highest_score,
        lowest_score=lowest_score,
        improvement_rate=improvement_rate,
        history=history_records
    )

@app.route("/upload", methods=["POST"])
def upload():
    """Extract, clean, create summaries, flashcards, and save to DB."""
    if "pdf" not in request.files:
        flash("No file part found in request.", "danger")
        return redirect(url_for("home"))

    files = request.files.getlist("pdf")
    if not files or all(file.filename == "" for file in files):
        flash("Please select at least one valid file or folder.", "warning")
        return redirect(url_for("home"))

    success_files = []
    fail_messages = []
    
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()

    for file in files:
        if file.filename == "":
            continue

        # Extract only the base name in case directories are passed
        base_filename = os.path.basename(file.filename)
        if not allowed_file(base_filename):
            # Ignore hidden files like OS metadata/DS_Store inside folders
            if base_filename.startswith('.'):
                continue
            fail_messages.append(f"'{base_filename}' format is not supported.")
            continue

        from werkzeug.utils import secure_filename
        filename = secure_filename(base_filename)
        if not filename:
            filename = f"file_{int(datetime.now().timestamp())}_{base_filename}"
            
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        
        try:
            file.save(filepath)
            text = extract_clean_text_from_file(filepath)
            
            # Generate Summaries
            det, sh, rev, op = generate_summaries(text)
            
            # Save material to DB
            cursor.execute("""
                INSERT INTO materials (filename, filepath, extracted_text, summary_detailed, summary_short, summary_revision, summary_onepage)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (filename, filepath, text, det, sh, rev, op))
            material_id = cursor.lastrowid
            
            # Generate and save flashcards
            cards = generate_flashcards(text)
            for card in cards:
                cursor.execute("""
                    INSERT INTO flashcards (material_id, front, back)
                    VALUES (?, ?, ?)
                """, (material_id, card.get("front", "No Question"), card.get("back", "No Answer")))
                
            success_files.append(base_filename)
        except Exception as e:
            logger.error(f"Failed to process '{base_filename}': {e}")
            fail_messages.append(f"Failed to process '{base_filename}': {str(e)}")

    conn.commit()
    conn.close()

    if success_files:
        if len(success_files) == 1:
            success_msg = f"Successfully uploaded and processed '{success_files[0]}'!"
        elif len(success_files) == 2:
            success_msg = f"Successfully uploaded and processed '{success_files[0]}' and '{success_files[1]}'!"
        else:
            success_msg = f"Successfully uploaded and processed {', '.join(f"'{f}'" for f in success_files[:-1])}, and '{success_files[-1]}'!"
        flash(success_msg, "success")
    if fail_messages:
        for msg in fail_messages:
            flash(msg, "danger")

    return redirect(url_for("home"))

@app.route("/summary/<int:material_id>")
def summary(material_id):
    """Render the 4 generated summary types, auto-regenerating if previously failed."""
    conn = get_db_connection()
    mat = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
    
    if not mat:
        conn.close()
        flash("Material not found.", "danger")
        return redirect(url_for("home"))
        
    # Self-heal check: if summaries were failed placeholders, regenerate them
    if (not mat["summary_detailed"] or "Error generating summary." in mat["summary_detailed"] or
        not mat["summary_short"] or "Error generating summary." in mat["summary_short"]):
        logger.info(f"Summary for material {material_id} is missing or broken. Regenerating on the fly...")
        try:
            det, sh, rev, op = generate_summaries(mat["extracted_text"])
            conn.execute("""
                UPDATE materials 
                SET summary_detailed = ?, summary_short = ?, summary_revision = ?, summary_onepage = ?
                WHERE id = ?
            """, (det, sh, rev, op, material_id))
            conn.commit()
            # Fetch updated record
            mat = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
            flash("Summaries regenerated successfully!", "success")
        except Exception as e:
            logger.error(f"Failed to regenerate summaries on the fly: {e}")
            flash("Summaries could not be generated at this moment. Groq API might be experiencing high traffic.", "warning")

    conn.close()
    return render_template("summary.html", material=mat)

@app.route("/flashcards/<int:material_id>")
def flashcards(material_id):
    """Interactive player for generated flashcards, auto-regenerating if none exist."""
    conn = get_db_connection()
    mat = conn.execute("SELECT filename, extracted_text FROM materials WHERE id = ?", (material_id,)).fetchone()
    
    if not mat:
        conn.close()
        flash("Material not found.", "danger")
        return redirect(url_for("home"))
        
    cards = conn.execute("SELECT front, back FROM flashcards WHERE material_id = ?", (material_id,)).fetchall()
    
    # Self-heal check: if no flashcards exist, try to generate them on the fly
    if not cards:
        logger.info(f"No flashcards found for material {material_id}. Generating on the fly...")
        try:
            generated_cards = generate_flashcards(mat["extracted_text"])
            for card in generated_cards:
                conn.execute("""
                    INSERT INTO flashcards (material_id, front, back)
                    VALUES (?, ?, ?)
                """, (material_id, card.get("front", "No Question"), card.get("back", "No Answer")))
            conn.commit()
            # Re-fetch cards
            cards = conn.execute("SELECT front, back FROM flashcards WHERE material_id = ?", (material_id,)).fetchall()
            if cards:
                flash("Flashcards generated successfully!", "success")
        except Exception as e:
            logger.error(f"Failed to generate flashcards on the fly: {e}")
            flash("Flashcards could not be generated at this moment. Groq API might be experiencing high traffic.", "warning")

    conn.close()
    cards_list = [dict(c) for c in cards]
    return render_template("flashcards.html", filename=mat["filename"], cards=cards_list)

@app.route("/quiz/config/<int:material_id>")
def quiz_config(material_id):
    """Setup quiz settings."""
    conn = get_db_connection()
    mat = conn.execute("SELECT id, filename FROM materials WHERE id = ?", (material_id,)).fetchone()
    conn.close()
    if not mat:
        flash("Material not found.", "danger")
        return redirect(url_for("home"))
    return render_template("quiz_setup.html", material=mat)

@app.route("/quiz/take", methods=["GET"])
def quiz_take():
    """Fetch/generate MCQ questions via Groq."""
    material_id = request.args.get("material_id")
    difficulty = request.args.get("difficulty", "Medium")
    count = int(request.args.get("count", 5))

    conn = get_db_connection()
    mat = conn.execute("SELECT filename, extracted_text FROM materials WHERE id = ?", (material_id,)).fetchone()
    conn.close()

    if not mat:
        flash("Material not found.", "danger")
        return redirect(url_for("home"))

    try:
        quiz_data = generate_quiz(mat["extracted_text"], difficulty, count)
        if not quiz_data:
            raise ValueError("Empty or invalid quiz generated by AI.")
    except Exception as e:
        flash(f"Quiz generation failed: {str(e)}", "danger")
        return redirect(url_for("home"))

    # Save to session to validate upon submission
    session["active_quiz"] = quiz_data
    session["active_filename"] = mat["filename"]
    session["active_difficulty"] = difficulty

    return render_template(
        "quiz.html",
        quiz=enumerate(quiz_data),
        difficulty=difficulty,
        filename=mat["filename"],
        total=len(quiz_data)
    )

@app.route("/quiz/submit", methods=["POST"])
def quiz_submit():
    """Score quiz, generate personalized study plans, weak topics, and tutor tutoring review."""
    quiz_data = session.get("active_quiz")
    filename = session.get("active_filename", "Notes")
    difficulty = session.get("active_difficulty", "Medium")

    if not quiz_data:
        flash("Quiz session expired. Please start a new quiz.", "warning")
        return redirect(url_for("home"))

    score = 0
    total = len(quiz_data)
    user_answers = {}
    
    for idx, q in enumerate(quiz_data):
        ans = request.form.get(f"q{idx}", "").strip()
        user_answers[f"q{idx}"] = ans
        if ans == q["answer"]:
            score += 1

    percentage = round((score / total) * 100, 1)

    # single Groq agent call to analyze and generate tutor review feedback, weak topic breakdown and study schedules
    analysis = generate_tutor_analytics_and_study_plans(quiz_data, user_answers)

    # Save details into SQLite Database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO quiz_results (
                username, filename, topic, difficulty, score, total, percentage, 
                weak_topics, study_plan_1d, study_plan_3d, study_plan_7d, 
                readiness_score, confidence, tutor_feedback
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["username"],
            filename,
            filename.rsplit(".", 1)[0],
            difficulty,
            score,
            total,
            percentage,
            json.dumps(analysis.get("weak_topics")),
            json.dumps(analysis.get("study_plan_1d")),
            json.dumps(analysis.get("study_plan_3d")),
            json.dumps(analysis.get("study_plan_7d")),
            analysis.get("readiness_score", 50),
            analysis.get("confidence", "Medium"),
            json.dumps(analysis.get("tutor_feedback"))
        ))
        result_id = cursor.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to record quiz results: {e}")
        flash("Result could not be archived in the history logs, showing local calculations.", "warning")
        result_id = 0

    # Build review structure for displaying
    review = []
    tutor_feedback = analysis.get("tutor_feedback", {})
    for idx, q in enumerate(quiz_data):
        user_ans = user_answers.get(f"q{idx}", "Not Answered")
        feedback = tutor_feedback.get(str(idx)) or tutor_feedback.get(idx)
        review.append({
            "question": q["question"],
            "options": q["options"],
            "correct_answer": q["answer"],
            "user_answer": user_ans,
            "is_correct": user_ans == q["answer"],
            "feedback": feedback
        })

    # Clear active session quiz keys
    session.pop("active_quiz", None)

    return render_template(
        "result.html",
        result_id=result_id,
        score=score,
        total=total,
        percentage=percentage,
        filename=filename,
        difficulty=difficulty,
        weak_topics=analysis.get("weak_topics", []),
        readiness_score=analysis.get("readiness_score", 50),
        confidence=analysis.get("confidence", "Medium"),
        recommendations=analysis.get("recommendations", "Review material chapters."),
        review=review
    )

@app.route("/study-plan/<int:result_id>")
def study_plan(result_id):
    """View generated Personalized Study Plans (1D, 3D, 7D schedules)."""
    conn = get_db_connection()
    res = conn.execute("SELECT filename, study_plan_1d, study_plan_3d, study_plan_7d FROM quiz_results WHERE id = ?", (result_id,)).fetchone()
    conn.close()
    
    if not res:
        flash("Performance report record not found.", "danger")
        return redirect(url_for("home"))

    try:
        plan_1d = json.loads(res["study_plan_1d"]) if res["study_plan_1d"] else []
        plan_3d = json.loads(res["study_plan_3d"]) if res["study_plan_3d"] else []
        plan_7d = json.loads(res["study_plan_7d"]) if res["study_plan_7d"] else []
    except Exception:
        plan_1d, plan_3d, plan_7d = [], [], []

    return render_template(
        "study_plan.html",
        filename=res["filename"],
        plan_1d=plan_1d,
        plan_3d=plan_3d,
        plan_7d=plan_7d
    )

@app.route("/leaderboard")
def leaderboard():
    """Rank system based on aggregate calculations from database."""
    conn = get_db_connection()
    leaderboard_data = conn.execute("""
        SELECT 
            username,
            COUNT(*) as quizzes_taken,
            ROUND(AVG(percentage), 1) as avg_score,
            MAX(percentage) - MIN(percentage) as improvement
        FROM quiz_results
        GROUP BY username
        ORDER BY avg_score DESC, quizzes_taken DESC
    """).fetchall()
    
    # Generate mock students to populate if only 1 student exists
    ranks = []
    for idx, row in enumerate(leaderboard_data):
        ranks.append({
            "rank": idx + 1,
            "username": row["username"],
            "quizzes_taken": row["quizzes_taken"],
            "avg_score": row["avg_score"],
            "improvement": max(0, row["improvement"])
        })
        
    # Append mock ranks to look like a true competitive SaaS leader board
    if len(ranks) < 4:
        mock_students = [
            {"rank": len(ranks)+1, "username": "Sahana M", "quizzes_taken": 12, "avg_score": 92.5, "improvement": 15.0},
            {"rank": len(ranks)+2, "username": "Sujay S", "quizzes_taken": 10, "avg_score": 88.2, "improvement": 12.4},
            {"rank": len(ranks)+3, "username": "Sahana H C", "quizzes_taken": 8, "avg_score": 81.0, "improvement": 9.5}
        ]
        ranks.extend(mock_students)
        ranks.sort(key=lambda x: x["avg_score"], reverse=True)
        for i, r in enumerate(ranks):
            r["rank"] = i + 1

    conn.close()
    return render_template("leaderboard.html", ranks=ranks)

@app.route("/certificate/<int:result_id>")
def certificate(result_id):
    """Generate and view student achievement certificate."""
    conn = get_db_connection()
    res = conn.execute("SELECT username, filename, score, total, percentage, timestamp FROM quiz_results WHERE id = ?", (result_id,)).fetchone()
    conn.close()

    if not res:
        flash("Quiz record not found.", "danger")
        return redirect(url_for("home"))

    if res["percentage"] < 80.0:
        flash("Achievement certificate requires a score of 80% or higher.", "warning")
        return redirect(url_for("home"))

    # Format timestamp
    try:
        dt = datetime.strptime(res["timestamp"], "%Y-%m-%d %H:%M:%S")
        date_str = dt.strftime("%B %d, %Y")
    except Exception:
        date_str = str(res["timestamp"])

    return render_template(
        "certificate.html",
        username=res["username"],
        percentage=res["percentage"],
        score=res["score"],
        total=res["total"],
        filename=res["filename"].rsplit(".", 1)[0],
        date=date_str
    )

@app.route("/clear-history", methods=["POST"])
def clear_history():
    """Wipes SQLite tables to clear test statistics."""
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM quiz_results")
        conn.commit()
        conn.close()
        flash("All quiz analytics and test history successfully cleared.", "success")
    except Exception as e:
        flash(f"Failed to reset records: {str(e)}", "danger")
    return redirect(url_for("home"))

# ==========================================================================
# CHART ANALYTICS ENDPOINT (API FOR CHART.JS)
# ==========================================================================
@app.route("/api/analytics")
def api_analytics():
    """Retrieve raw historical statistics to draw charts on dashboard."""
    username = session.get("username", "Sujay")
    conn = get_db_connection()
    records = conn.execute("""
        SELECT percentage, readiness_score, timestamp, difficulty, filename
        FROM quiz_results
        WHERE username = ?
        ORDER BY id ASC
    """, (username,)).fetchall()
    conn.close()

    timeline = []
    readiness = []
    labels = []
    
    for idx, r in enumerate(records):
        timeline.append(r["percentage"])
        readiness.append(r["readiness_score"] or 50)
        labels.append(f"Quiz #{idx+1} ({r['filename'][:10]})")

    # If database is empty, return initial onboarding data to render clean empty charts
    if not timeline:
        labels = ["Quiz #1 (Sample)", "Quiz #2 (Sample)", "Quiz #3 (Sample)"]
        timeline = [60, 75, 90]
        readiness = [55, 70, 85]

    return jsonify({
        "labels": labels,
        "scores": timeline,
        "readiness": readiness
    })

# ==========================================================================
# SPACED REPETITION FLASHCARDS
# ==========================================================================
@app.route("/spaced-repetition")
def flashcards_spaced():
    """Spaced repetition review system for all flashcards."""
    conn = get_db_connection()
    all_cards = conn.execute("""
        SELECT f.id, f.front, f.back, f.material_id, m.filename
        FROM flashcards f
        JOIN materials m ON f.material_id = m.id
        ORDER BY RANDOM()
        LIMIT 30
    """).fetchall()
    materials = conn.execute("SELECT id, filename FROM materials ORDER BY id DESC").fetchall()
    conn.close()
    cards_list = [dict(c) for c in all_cards]
    return render_template("spaced_repetition.html", cards=cards_list, materials=materials)

# ==========================================================================
# GPA / SEMESTER PREDICTOR
# ==========================================================================
@app.route("/gpa-predictor")
def semester_predictor():
    """GPA prediction tool based on quiz performance data."""
    username = session.get("username", "Sujay")
    conn = get_db_connection()
    records = conn.execute("""
        SELECT filename, topic, difficulty, score, total, percentage, readiness_score, timestamp
        FROM quiz_results
        WHERE username = ?
        ORDER BY id DESC
    """, (username,)).fetchall()
    conn.close()

    # Calculate predicted GPA based on quiz performance
    if records:
        avg_pct = sum(r["percentage"] for r in records) / len(records)
        # Map percentage to GPA (simple linear mapping)
        predicted_gpa = round(min(10.0, (avg_pct / 100) * 10), 2)
        grade = "O" if avg_pct >= 90 else "A+" if avg_pct >= 80 else "A" if avg_pct >= 70 else "B+" if avg_pct >= 60 else "B" if avg_pct >= 50 else "C"
    else:
        predicted_gpa = 0
        avg_pct = 0
        grade = "-"

    return render_template(
        "gpa_predictor.html",
        records=records,
        predicted_gpa=predicted_gpa,
        avg_pct=round(avg_pct, 1),
        grade=grade,
        total_assessments=len(records)
    )

# ==========================================================================
# CAREER READINESS NAVIGATOR
# ==========================================================================
@app.route("/career-navigator")
def career_navigator():
    """Career readiness assessment based on learning profile."""
    username = session.get("username", "Sujay")
    conn = get_db_connection()
    records = conn.execute("""
        SELECT filename, topic, difficulty, percentage, readiness_score, weak_topics
        FROM quiz_results
        WHERE username = ?
        ORDER BY id DESC
    """, (username,)).fetchall()
    conn.close()

    # Calculate career readiness metrics
    if records:
        avg_readiness = round(sum((r["readiness_score"] or 50) for r in records) / len(records), 1)
        topics_covered = len(set(r["topic"] for r in records))
        hard_quizzes = sum(1 for r in records if r["difficulty"] == "Hard")
        avg_pct = round(sum(r["percentage"] for r in records) / len(records), 1)
    else:
        avg_readiness = 0
        topics_covered = 0
        hard_quizzes = 0
        avg_pct = 0

    # Career readiness tiers
    if avg_readiness >= 85:
        readiness_tier = "Industry Ready"
        tier_color = "success"
    elif avg_readiness >= 65:
        readiness_tier = "Developing"
        tier_color = "warning"
    else:
        readiness_tier = "Foundational"
        tier_color = "danger"

    return render_template(
        "career_navigator.html",
        avg_readiness=avg_readiness,
        topics_covered=topics_covered,
        hard_quizzes=hard_quizzes,
        avg_pct=avg_pct,
        readiness_tier=readiness_tier,
        tier_color=tier_color,
        total_assessments=len(records)
    )

# ==========================================================================
# AI RESEARCH ASSISTANT LAB
# ==========================================================================
@app.route("/research-lab")
def research_lab():
    """AI-powered research assistant for study materials."""
    conn = get_db_connection()
    materials = conn.execute("SELECT id, filename, created_at FROM materials ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("research_lab.html", materials=materials)

@app.route("/research-lab/ask", methods=["POST"])
def research_ask():
    """Ask a question about uploaded materials using AI."""
    material_id = request.form.get("material_id")
    question = request.form.get("question", "").strip()

    if not question:
        return jsonify({"error": "Please enter a question."}), 400

    conn = get_db_connection()
    if material_id and material_id != "all":
        mat = conn.execute("SELECT extracted_text, filename FROM materials WHERE id = ?", (material_id,)).fetchone()
        context = mat["extracted_text"][:6000] if mat else ""
        source = mat["filename"] if mat else "Unknown"
    else:
        all_mats = conn.execute("SELECT extracted_text, filename FROM materials").fetchall()
        context = " ".join([m["extracted_text"][:3000] for m in all_mats])[:8000]
        source = "All Materials"
    conn.close()

    if not context:
        return jsonify({"error": "No study materials found. Upload a PDF first."}), 400

    try:
        system_prompt = "You are an expert academic tutor. Answer the student's question based on their study materials. Be thorough, use examples, and format your response with clear sections."
        user_prompt = f"Study Material Context:\n{context}\n\nStudent Question: {question}"
        answer = call_groq_with_fallback(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=2000
        )
        return jsonify({"answer": answer, "source": source})
    except Exception as e:
        logger.error(f"Research lab AI error: {e}")
        return jsonify({"error": f"AI processing failed: {str(e)}"}), 500

# ==========================================================================
# ADMIN PANEL
# ==========================================================================
@app.route("/admin")
def admin_panel():
    """Admin dashboard for managing materials, quiz results, and system stats."""
    conn = get_db_connection()
    materials = conn.execute("SELECT id, filename, created_at FROM materials ORDER BY id DESC").fetchall()
    total_materials = len(materials)
    
    quiz_stats = conn.execute("""
        SELECT COUNT(*) as total, AVG(percentage) as avg_pct, 
               MAX(percentage) as max_pct, MIN(percentage) as min_pct
        FROM quiz_results
    """).fetchone()
    
    total_flashcards = conn.execute("SELECT COUNT(*) as cnt FROM flashcards").fetchone()["cnt"]
    total_quizzes = quiz_stats["total"] or 0
    avg_pct = round(quiz_stats["avg_pct"], 1) if quiz_stats["avg_pct"] else 0
    
    recent_results = conn.execute("""
        SELECT id, username, filename, difficulty, score, total, percentage, timestamp
        FROM quiz_results ORDER BY id DESC LIMIT 20
    """).fetchall()
    
    conn.close()

    return render_template(
        "admin_panel.html",
        materials=materials,
        total_materials=total_materials,
        total_flashcards=total_flashcards,
        total_quizzes=total_quizzes,
        avg_pct=avg_pct,
        recent_results=recent_results
    )

@app.route("/admin/delete-material/<int:material_id>", methods=["POST"])
def delete_material(material_id):
    """Delete a material and its flashcards."""
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM flashcards WHERE material_id = ?", (material_id,))
        conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))
        conn.commit()
        conn.close()
        flash("Material and associated flashcards deleted.", "success")
    except Exception as e:
        flash(f"Delete failed: {str(e)}", "danger")
    return redirect(url_for("admin_panel"))

# ==========================================================================
# CUSTOM TEMPLATE FILTERS
# ==========================================================================
@app.template_filter("format_datetime")
def format_datetime(value):
    try:
        if isinstance(value, str):
            dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        else:
            dt = value
        return dt.strftime("%b %d, %Y • %I:%M %p")
    except Exception:
        return str(value)

# ==========================================
# ERROR INTERCEPTORS
# ==========================================
@app.errorhandler(413)
def file_too_large(e):
    flash("The uploaded PDF notes exceed the maximum limit of 32 MB.", "danger")
    return redirect(url_for("home"))

@app.errorhandler(404)
def route_not_found(e):
    return redirect(url_for("home"))

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Internal crash: {e}")
    return render_template("index.html"), 500

# ==========================================================================
# APPLICATION ENTRYPOINT
# ==========================================================================
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)