# Smart Resume Screener - Backend

A production-grade, modular backend API for the **Smart Resume Screener** platform built with **Python 3**, **FastAPI**, **SQLAlchemy 2.0 (Async)**, and **PostgreSQL** (with SQLite fallback for instant zero-dependency local development).

---

## 📁 Project Architecture

```
smart_resume_screener/
├── docker-compose.yml              # PostgreSQL + FastAPI container orchestration
├── .gitignore
├── README.md
└── backend/
    ├── Dockerfile
    ├── requirements.txt            # Python dependencies
    ├── .env.example                # Environment variables template
    ├── .env                        # Local active environment configuration
    ├── alembic.ini                 # Migration tool configuration
    ├── alembic/                    # Database migrations
    │   ├── env.py
    │   ├── script.py.mako
    │   └── versions/
    └── app/
        ├── main.py                 # Application factory & lifespan
        ├── core/                   # Core configuration & infrastructure
        │   ├── config.py           # Pydantic Settings & environment loader
        │   ├── database.py         # Async SQLAlchemy Engine & SessionLocal
        │   ├── security.py         # Passlib (bcrypt) & JWT helpers
        │   └── exceptions.py       # Standardized domain HTTP exceptions
        ├── models/                 # SQLAlchemy ORM Database Models
        │   ├── __init__.py
        │   ├── base.py             # Declarative Base & Timestamp mixin
        │   ├── user.py             # User & UserRole models
        │   ├── job.py              # JobDescription model
        │   ├── candidate.py        # Candidate personal & social profile
        │   ├── resume.py           # Parsed Resume & JSON schema structures
        │   └── screening_result.py # Match scores & application status
        ├── schemas/                # Pydantic v2 DTOs (Data Transfer Objects)
        │   ├── __init__.py
        │   ├── user.py             # Auth & User schemas
        │   ├── job.py              # Job creation, update, & response schemas
        │   ├── candidate.py        # Candidate profile schemas
        │   ├── resume.py           # Parsed resume structures & upload DTOs
        │   └── screening_result.py # Screening, ranking, & feedback schemas
        ├── repositories/           # Data Access Layer (Repository Pattern)
        │   ├── base.py             # Generic async CRUD operations
        │   ├── user_repository.py
        │   ├── job_repository.py
        │   ├── candidate_repository.py
        │   ├── resume_repository.py
        │   └── screening_repository.py
        ├── services/               # Business Logic Layer
        │   ├── user_service.py     # Auth, hashing, token issuance
        │   ├── job_service.py      # Job posting & authorization rules
        │   └── resume_service.py   # Upload handling, candidate linking, screening
        └── api/                    # Presentation / Routing Layer
            ├── deps.py             # Auth & Database dependency injection
            └── v1/
                ├── router.py       # Combined API v1 router
                └── endpoints/
                    ├── auth.py     # /api/v1/auth (register, login, me)
                    ├── jobs.py     # /api/v1/jobs (CRUD job descriptions)
                    ├── resumes.py  # /api/v1/resumes (upload & retrieve)
                    └── screening.py# /api/v1/screening (screen & rank candidates)
```

---

## 🗄️ Database Schema Design

The relational and document hybrid schema connects **Users (Recruiters)**, **Job Descriptions**, **Candidates**, **Parsed Resumes**, and **Screening Results (Match Ratings)**:

```
[ User (Recruiter) ]
       │ 1:N
       ▼
[ JobDescription ] ───┐
                      │ 1:N
                      ▼
[ Candidate ] ──1:N──> [ Resume ] ───1:N───> [ ScreeningResult ] (Ranked Matches)
```

### 1. `users`
* `id` (PK, Integer)
* `email` (String, Unique, Indexed)
* `hashed_password` (String)
* `full_name` (String)
* `role` (Enum: `admin`, `recruiter`, `hiring_manager`)
* `company_name` (String, Optional)
* `is_active` (Boolean)
* `created_at`, `updated_at` (Timestamps)

### 2. `job_descriptions`
* `id` (PK, Integer)
* `user_id` (FK -> `users.id`)
* `title` (String, Indexed)
* `department` (String)
* `location` (String)
* `employment_type` (Enum: `full_time`, `part_time`, `contract`, `internship`, `remote`)
* `experience_level` (Enum: `entry_level`, `mid_level`, `senior_level`, `lead`, `executive`)
* `min_years_experience` / `max_years_experience` (Integer)
* `description_raw` (Text)
* `responsibilities` (Text)
* `qualifications` (Text)
* `required_skills` (JSON array: `["Python", "FastAPI", "PostgreSQL", ...]`)
* `preferred_skills` (JSON array: `["Docker", "NLP", "LLMs", ...]`)
* `is_active` (Boolean)
* `created_at`, `updated_at` (Timestamps)

### 3. `candidates`
* `id` (PK, Integer)
* `full_name` (String, Indexed)
* `email` (String, Unique, Indexed)
* `phone` (String)
* `location` (String)
* `linkedin_url`, `github_url`, `portfolio_url` (String)
* `total_experience_years` (Float)
* `created_at`, `updated_at` (Timestamps)

### 4. `resumes`
* `id` (PK, Integer)
* `candidate_id` (FK -> `candidates.id`)
* `file_name` (String)
* `file_path` (String)
* `file_type` (String: `pdf`, `docx`, `txt`)
* `file_size_bytes` (BigInteger)
* `parsing_status` (Enum: `pending`, `processing`, `completed`, `failed`)
* `raw_text` (Text, Optional)
* `summary` (Text, Optional)
* `skills` (JSON array of parsed skills)
* `work_experiences` (JSON array of structured work items: company, position, dates, bullets, tech)
* `education` (JSON array of degrees, institutions, years, GPA)
* `certifications` (JSON array)
* `languages` (JSON array)
* `parsed_metadata` (JSON: model version, token count, extraction metrics)
* `error_message` (Text, Optional)
* `created_at`, `updated_at` (Timestamps)

### 5. `screening_results`
* `id` (PK, Integer)
* `job_id` (FK -> `job_descriptions.id`)
* `resume_id` (FK -> `resumes.id`)
* `match_score` (Float, 0.0 - 100.0, Indexed)
* `skills_match_score` (Float)
* `experience_match_score` (Float)
* `education_match_score` (Float)
* `analysis_summary` (Text)
* `matched_skills` (JSON array)
* `missing_skills` (JSON array)
* `detailed_feedback` (JSON dictionary)
* `status` (Enum: `applied`, `screened`, `shortlisted`, `interview`, `rejected`)
* `notes` (Text, Optional)
* `created_at`, `updated_at` (Timestamps)

---

## 🚀 Quick Start Guide

### 1. Local Python Setup (Zero Configuration with SQLite)

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the FastAPI development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Docker & PostgreSQL Setup

```bash
# In the project root:
docker-compose up --build -d
```

### 3. Interactive Documentation
Once started, open your browser to:
- **Interactive Swagger UI**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **ReDoc Alternative UI**: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
