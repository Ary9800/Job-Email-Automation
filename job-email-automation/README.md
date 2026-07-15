# Job Email Automation

Automate job applications from LinkedIn/Naukri screenshots **and** public LinkedIn recruiter posts. Extract recruiter email and job details, generate tailored application emails, attach your resume, preview, and send via SMTP.

## Features

- **Upload screenshots** — LinkedIn/Naukri job posts (batch)
- **Find on LinkedIn** — search public HR/recruiter posts (India, experience filters)
  - Time filter: **Past 1 day / 1 week / 1 month**
  - Experience: **2+ / 2–3 / 2–4 / 3+ / 3–5 / Any**
  - Skips job-seeker posts (“looking for job / open to work”)
  - Optional **SerpAPI** for more stable Google results (DuckDuckGo default)
  - **Fetch email from post** when snippet has no email
  - **LinkedIn bookmarklet** — select a post on LinkedIn → send to local app
- **Extract** — RapidOCR (local) + optional Ollama vision
- **Generate emails** — AI (Ollama) or static template; choose in preview
- **Subject** — `Application for {role} at {company}` (no experience years in role)
- **Send** — resume attached via Gmail/Outlook SMTP
- **Skip already-sent / duplicate URL / duplicate email**

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   React UI  │────▶│  FastAPI Backend │────▶│  RapidOCR (local)   │
│  (Vite)     │     │                  │     │  + Ollama (optional)│
└─────────────┘     │  - Upload        │     │  + DuckDuckGo search│
                    │  - Find LinkedIn │     └─────────────────────┘
                    │  - Extract       │
                    │  - Generate      │
                    │  - Send (SMTP)   │
                    └──────────────────┘
                              │
                              ▼
                     Gmail / Outlook SMTP
```

## Prerequisites

| Requirement | Notes |
|---|---|
| **Python 3.10+** | Backend |
| **Node.js 18+** | Frontend |
| **SMTP credentials** | Gmail App Password recommended |
| **Resume PDF** | Path set in `.env` or uploaded in UI |
| **Ollama** (optional) | Better AI emails; OCR works without it |

---

## How to run (quick start)

### 1. Backend

```bash
cd D:\job-email-automation\backend

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

copy .env.example .env
# Edit .env — set SENDER_*, SMTP_*, DEFAULT_RESUME_PATH

uvicorn app.main:app --reload --port 8000
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs  
Health: http://localhost:8000/api/health

### 2. Frontend (new terminal)

```bash
cd D:\job-email-automation\frontend

npm install
npm run dev
```

App: http://localhost:5173  
(If 5173 is busy, Vite uses 5174 — check the terminal.)

### 3. Optional — Ollama (better AI emails)

```bash
# Install from https://ollama.com then:
ollama pull llama3.2
ollama pull llama3.2-vision   # optional, for screenshot AI
```

Email extraction works with **RapidOCR only** (no Ollama).  
If Ollama is offline, the app uses the **static email template**.

---

## Configure once (`backend/.env`)

Copy from `.env.example` and fill in:

```env
# Your profile
SENDER_NAME=Your Name
SENDER_EMAIL=your.email@gmail.com
SENDER_PHONE=+91-XXXXXXXXXX

CANDIDATE_CURRENT_ROLE=Java Full Stack Developer
CANDIDATE_YEARS_EXPERIENCE=3+ years
CANDIDATE_KEY_SKILLS=Java, Spring Boot, REST APIs, SQL, and frontend frameworks
CANDIDATE_EXPERIENCE_SUMMARY=I have 3+ years of hands-on experience in Java Full Stack Application Development...

# SMTP (Gmail App Password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=your-16-char-gmail-app-password
SMTP_USE_TLS=true

# Resume — absolute path recommended
DEFAULT_RESUME_PATH=D:\job-email-automation\resume\Your_Resume.pdf
```

### Gmail App Password

1. Enable **2-Step Verification** on your Google account  
2. Google Account → **Security** → **App passwords**  
3. Create password for “Mail”  
4. Paste it as `SMTP_PASSWORD` (no spaces)

---

## Daily usage

### A) From screenshots

1. Open http://localhost:5173  
2. Confirm **Config Ready** badge (SMTP + sender + resume from `.env`)  
3. **Upload Screenshots** tab → drop LinkedIn/Naukri images  
4. Select jobs with checkboxes (Select all available)  
5. Click **Extract & Generate**  
6. **Review & Send** → pick AI or Static → edit if needed → **Approve & Send**

### B) Find on LinkedIn (no screenshot)

1. Open **Find on LinkedIn** tab  
2. Choose **Posted:** Past 1 day / Past 1 week / Past 1 month  
3. Choose **Experience:** 2+, 2–3, 2–4, 3+, 3–5, or Any  
4. Select roles to search  
5. Click **Search LinkedIn Posts**  
6. Select posts → **Import & Generate** (emails auto-generated when email is found)  
7. Duplicate LinkedIn URLs / recruiter emails are skipped automatically  
8. If a post has **No email**, click **Fetch email from post**, or open it on LinkedIn → copy text → **Paste post**  
9. Optional: install the **LinkedIn bookmarklet** — http://localhost:8000/api/find-jobs/bookmarklet  
10. **Review & Send** as usual  

### C) LinkedIn bookmarklet (while browsing LinkedIn)

1. Open http://localhost:8000/api/find-jobs/bookmarklet  
2. Drag **Send to Job Email App** to your bookmarks bar  
3. On LinkedIn, select hiring-post text → click the bookmark  
4. Open the app → Review & Send  

> Full LinkedIn login automation is **not** included (account risk). Bookmarklet + search + paste is the safe Phase 2 approach.

### Optional: SerpAPI (better search)

Add to `backend/.env`:

```env
SERPAPI_API_KEY=your_key_here
```

Without it, search uses free DuckDuckGo.  

Already-**sent** jobs are skipped on the next Extract & Generate.

---

## Phase 3 — Tracker, analytics, daily run, multi-resume

### Tracker & Analytics tab
- See sent / replied / interview counts and reply rate
- Breakdown by role
- Update each application outcome: Waiting, Replied, Interview, Rejected, Hired, No response
- Sent emails auto-mark as **waiting**

### Daily auto-run
1. Open **Tracker & Analytics**
2. Enable daily run, set hour/minute, posted window, experience
3. **Save schedule** — backend checks every minute
4. Or click **Run now** to search/import/generate immediately

### Multi-resume
1. Upload multiple PDFs via Settings (each gets a `resume_xxxx.pdf` name in `backend/resumes/`)
2. In Tracker → **Multi-resume**, map filenames + keywords (e.g. `backend, spring`)
3. On generate/send, matching role picks that resume automatically

### Role templates
Predefined in `backend/data/role_templates.json` (Java Backend / Full Stack). Matching keywords override the default static email body when generating.

---

## Project structure

```
job-email-automation/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── routers/          # jobs, config, find-jobs, phase3
│   │   └── services/         # extractor, email_*, linkedin_finder, ocr, scheduler
│   ├── data/                 # jobs.json, scheduler, templates, resume profiles
│   ├── resumes/
│   ├── uploads/
│   ├── .env                  # your secrets (do not commit)
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js
│   │   └── components/
│   └── package.json
└── README.md
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Backend won’t start / port 8000 in use | Stop other Python process or use `--port 8001` and update Vite proxy |
| Frontend can’t reach API | Backend must be on 8000; Vite proxies `/api` → `localhost:8000` |
| No recruiter email found | Crop clearer screenshot, or enter email manually on the job card |
| SMTP / Auth error | Use Gmail **App Password**, not your normal password |
| “Job not found” after restart | Jobs now persist to disk; if still missing, re-upload and Extract again |
| Find LinkedIn returns few results | Try **Past 1 month**; search depends on public web results |
| Bad company in subject | Re-run Extract & Generate — company is cleaned/inferred from email domain |
| Ollama Offline badge | Optional — static emails still work; start Ollama for AI drafts |

---

## API endpoints (reference)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Backend + Ollama status |
| `GET` | `/api/config` | Load profile/SMTP/resume from `.env` |
| `POST` | `/api/upload` | Upload screenshots |
| `POST` | `/api/process-batch` | Extract + generate for selected jobs |
| `POST` | `/api/find-jobs/search` | Search LinkedIn posts (`time_period`, `experience_range`) |
| `POST` | `/api/find-jobs/import` | Import + enrich missing emails + auto-generate |
| `POST` | `/api/find-jobs/enrich` | Fetch public post page for recruiter email |
| `POST` | `/api/find-jobs/paste` | Paste post URL/text → create job + generate |
| `POST` | `/api/find-jobs/bookmarklet-capture` | Capture from LinkedIn bookmarklet |
| `GET` | `/api/find-jobs/bookmarklet` | Bookmarklet install page |
| `POST` | `/api/jobs/{id}/send` | Send one approved email |
| `PATCH` | `/api/jobs/{id}/outcome` | Update application outcome |
| `GET` | `/api/analytics` | Tracker summary + by role/company |
| `GET/PUT` | `/api/scheduler` | Daily auto-run config |
| `POST` | `/api/scheduler/run-now` | Trigger search/import/generate now |
| `GET/PUT` | `/api/resumes/profiles` | Multi-resume role mapping |
| `GET/PUT` | `/api/templates/roles` | Role email templates |

Full interactive docs: http://localhost:8000/docs

---

## License

MIT
