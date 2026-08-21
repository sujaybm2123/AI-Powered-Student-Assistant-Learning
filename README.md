# 🎓 AI Student Learning Assistant

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1.1-000000?style=for-the-badge&logo=flask&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-AI_Powered-F55036?style=for-the-badge&logo=groq&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Ready-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**An intelligent, AI-powered web application that transforms your study materials into interactive learning experiences — summaries, flashcards, quizzes, study plans, and more.**

[🐛 Report Bug](https://github.com/sneha-s2005/ai-student-learning-assistant/issues) · [✨ Request Feature](https://github.com/sneha-s2005/ai-student-learning-assistant/issues)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Environment Variables](#environment-variables)
  - [Running Locally](#running-locally)
- [Project Structure](#-project-structure)
- [API Reference](#-api-reference)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🌟 Overview

The **AI Student Learning Assistant** is a full-stack Flask web application that leverages **Groq's ultra-fast LLM inference** to help students learn smarter. Upload any study material — PDF, DOCX, TXT, Markdown, or even images — and the AI instantly generates:

- 📝 Multiple summary styles (Detailed, Short, Revision, One-Page Notes)
- 🃏 Interactive flashcards for spaced repetition
- 🧠 Adaptive quizzes with configurable difficulty
- 📊 Personalized performance analytics & study plans
- 🎓 AI tutor feedback on incorrect answers

---

## ✨ Features

| Feature | Description |
|---|---|
| **📁 Multi-format Upload** | Supports PDF, DOCX, DOC, TXT, MD, PNG, JPG, JPEG files (up to 100MB) |
| **🤖 AI Summaries** | 4 auto-generated summary formats: Detailed, Short, Exam Revision, One-Page Notes |
| **🃏 Flashcards** | 20 AI-generated flashcards per material with an interactive flip card player |
| **📝 Adaptive Quizzes** | MCQ quizzes with Easy / Medium / Hard difficulty and custom question count |
| **📊 Performance Analytics** | Score tracking, weak topic identification, and improvement rate over time |
| **🗓 Study Plans** | Personalized 1-Day, 3-Day, and 7-Day study plans based on quiz performance |
| **🏆 Leaderboard** | Compare scores and track your ranking among peers |
| **🎓 Exam Readiness** | AI-calculated readiness score with confidence level and focus recommendations |
| **📖 AI Tutor Feedback** | Detailed explanation for every wrong answer with concept clarification and examples |
| **🔄 Self-healing** | Auto-regenerates broken summaries or missing flashcards on the fly |
| **🗺 Career Navigator** | AI-powered career pathway suggestions based on study topics |
| **🔬 Research Lab** | AI-assisted research exploration tool |
| **📈 GPA Predictor** | Estimate academic performance based on quiz analytics |
| **🏅 Certificates** | Downloadable achievement certificates on course completion |
| **🔁 Spaced Repetition** | Smart review scheduling to maximize long-term retention |
| **🌐 Dual DB Support** | SQLite for local development, PostgreSQL for production |

---

## 🛠 Tech Stack

### Backend
- **[Flask 3.1.1](https://flask.palletsprojects.com/)** — Lightweight Python web framework
- **[Groq SDK](https://console.groq.com/)** — Ultra-fast LLM inference (LLaMA 3.3 70B, LLaMA 3.1 8B, LLaMA 4 Scout Vision)
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** — PDF parsing and text extraction
- **[pypdf](https://pypdf.readthedocs.io/)** — Pure Python PDF reader (primary extractor)
- **[python-docx](https://python-docx.readthedocs.io/)** — Microsoft Word document parsing
- **[SQLite3](https://docs.python.org/3/library/sqlite3.html)** — Local development database
- **[psycopg2](https://www.psycopg.org/)** — PostgreSQL adapter for production
- **[Gunicorn](https://gunicorn.org/)** — WSGI production server

### Frontend
- **HTML5 / CSS3 / Vanilla JavaScript** — Clean, responsive UI
- **Jinja2** — Server-side templating

---


## 🚀 Getting Started

### Prerequisites

- Python **3.10+**
- A **[Groq API Key](https://console.groq.com/)** (free tier available)
- `pip` package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/sneha-s2005/ai-student-learning-assistant.git
   cd ai-student-learning-assistant
   ```

2. **Create and activate a virtual environment**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # macOS / Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Environment Variables

Create a `.env` file in the project root:

```env
# Required: Your Groq API key
GROQ_API_KEY=your_groq_api_key_here

# Optional: Flask secret key (auto-generated default used if not set)
FLASK_SECRET_KEY=your_secret_key_here

# Optional: PostgreSQL connection URL (SQLite used by default)
# DATABASE_URL=postgresql://user:password@host:5432/dbname
```

> ⚠️ **Never commit your `.env` file.** It is already in `.gitignore`.

### Running Locally

```bash
python app.py
```

Open your browser and navigate to `http://localhost:5000`

---

## 📁 Project Structure

```
ai-student-learning-assistant/
│
├── app.py                  # Main Flask application (routes, AI calls, DB logic)
├── requirements.txt        # Python dependencies
├── .gitignore              # Git exclusions
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html           # Base layout with navigation
│   ├── index.html          # Dashboard / Home page
│   ├── summary.html        # AI summary viewer
│   ├── flashcards.html     # Flashcard player
│   ├── quiz_setup.html     # Quiz configuration page
│   ├── quiz.html           # Quiz taking interface
│   ├── result.html         # Quiz results & analytics
│   ├── study_plan.html     # Personalized study plan
│   ├── leaderboard.html    # Score leaderboard
│   ├── certificate.html    # Completion certificate
│   ├── spaced_repetition.html  # Spaced repetition scheduler
│   ├── career_navigator.html   # AI career path navigator
│   ├── research_lab.html   # AI research assistant
│   ├── gpa_predictor.html  # GPA prediction tool
│   └── admin_panel.html    # Admin dashboard
│
├── static/                 # Static assets (CSS, JS, images)
├── uploads/                # Uploaded files (git-ignored)
└── database.db             # SQLite database (git-ignored)
```

---

## 🤖 AI Models Used

| Model | Usage |
|---|---|
| `llama-3.3-70b-versatile` | Primary model for summaries, flashcards, quizzes, study plans |
| `llama-3.1-8b-instant` | Fallback model when the primary model is unavailable |
| `meta-llama/llama-4-scout-17b-16e-instruct` | Vision model for OCR/image text extraction |

All models are served through **[Groq](https://groq.com/)** for industry-leading inference speeds.

---

## 🗃 Database Schema

### `materials`
Stores uploaded study files and their AI-generated summaries.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment ID |
| `filename` | TEXT | Original file name |
| `filepath` | TEXT | Server-side storage path |
| `extracted_text` | TEXT | Full text content extracted from file |
| `summary_detailed` | TEXT | Comprehensive AI summary |
| `summary_short` | TEXT | 2–3 sentence overview |
| `summary_revision` | TEXT | Exam-style bullet points |
| `summary_onepage` | TEXT | Cheat-sheet style notes |
| `created_at` | DATETIME | Upload timestamp |

### `flashcards`
AI-generated flashcard pairs linked to study materials.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment ID |
| `material_id` | INTEGER FK | Reference to `materials.id` |
| `front` | TEXT | Question or concept |
| `back` | TEXT | Answer, definition, or formula |

### `quiz_results`
Stores all quiz attempts with performance analytics.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment ID |
| `username` | TEXT | Student name |
| `filename` | TEXT | Source material name |
| `topic` | TEXT | Quiz topic |
| `difficulty` | TEXT | Easy / Medium / Hard |
| `score` | INTEGER | Correct answers |
| `total` | INTEGER | Total questions |
| `percentage` | REAL | Score percentage |
| `weak_topics` | TEXT | JSON: identified weak areas |
| `study_plan_1d` | TEXT | JSON: 1-day study plan |
| `study_plan_3d` | TEXT | JSON: 3-day study plan |
| `study_plan_7d` | TEXT | JSON: 7-day study plan |
| `readiness_score` | INTEGER | Exam readiness (0–100) |
| `confidence` | TEXT | Low / Medium / High |
| `tutor_feedback` | TEXT | JSON: per-question AI explanations |
| `timestamp` | DATETIME | Quiz submission time |

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

Please make sure to update tests as appropriate and follow the existing code style.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- [Groq](https://groq.com/) for blazing-fast LLM inference
- [Meta AI](https://ai.meta.com/) for the LLaMA model family
- [Flask](https://flask.palletsprojects.com/) for the lightweight web framework
- [PyMuPDF](https://pymupdf.readthedocs.io/) for reliable PDF text extraction

---

<div align="center">

Made with ❤️ by **[Sneha S](https://github.com/sneha-s2005)**

⭐ Star this repo if you found it helpful!

</div>
