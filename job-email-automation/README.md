# Job Email Automation

Automate job applications from LinkedIn and Naukri screenshots. Upload job post screenshots, extract recruiter email and job details using **local Ollama AI** (no API key), generate tailored application emails, attach your resume, and send — all in batch.

## What it does

1. **Upload screenshots** — Drop as many LinkedIn/Naukri job post screenshots as you want
2. **AI extraction** — Ollama vision model reads each screenshot to find email, role, company, skills, and job description
3. **Email generation** — Fills your template with dynamic fields plus an AI-written paragraph based on the job post
4. **Preview & approve** — Review and edit each email before sending
5. **Resume attachment** — Attaches your resume (PDF/DOC) to every email

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   React UI  │────▶│  FastAPI Backend │────▶│  Ollama (local)     │
│  (Vite)     │     │                  │     │  llama3.2-vision    │
└─────────────┘     │  - Upload        │     │  (read screenshots) │
                    │  - Extract       │     │  llama3.2           │
                    │  - Generate      │     │  (write emails)     │
                    │  - Send (SMTP)   │     └─────────────────────┘
                    └──────────────────┘
                              │
                              ▼
                     Gmail / Outlook SMTP
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) installed and running (free, local, no API key)
- SMTP credentials (Gmail App Password recommended)

## Setup

### 1. Install & start Ollama

Download from https://ollama.com and install.

Pull the required models (one-time, ~5-8 GB total):

```bash
ollama pull llama3.2-vision
ollama pull llama3.2
```

Ollama runs automatically after install. Verify:

```bash
ollama list
```

**Alternative vision models** (if `llama3.2-vision` is slow on your PC):

```bash
ollama pull llava        # smaller, faster
ollama pull moondream    # smallest, fastest (less accurate)
```

Then set in `backend/.env`:

```env
OLLAMA_VISION_MODEL=llava
```

### 2. Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Check AI status: http://localhost:8000/api/health

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — badge should show **Ollama Ready**.

## Is Ollama capable enough?

| Task | Ollama | Notes |
|---|---|---|
| Read screenshot text | Yes | `llama3.2-vision` or `llava` read LinkedIn/Naukri posts well |
| Extract email, role, company | Yes | Works for clear screenshots |
| Understand job requirements | Yes | Extracts skills, experience, responsibilities |
| Write tailored email paragraph | Yes | `llama3.2` writes good application emails |
| Complex/blurry screenshots | Partial | May miss details — user can edit in preview |

**Tips for best results:**
- Use clear, full screenshots (not cropped too tight)
- Fill in your **Profile** in Settings (skills, experience) so AI tailors emails better
- Always use **Preview & Send** to verify before sending
- If slow, switch to `llava` or `moondream` vision model

## Usage

1. **Settings → Profile** — Name, email, phone, resume, and your skills/experience
2. **Settings → Email** — SMTP credentials
3. **Settings → Template** — Email subject/body template
4. **Upload screenshots** — Drag & drop job post screenshots
5. **Extract & Generate** — AI reads screenshots and writes emails
6. **Review & Send** — Preview each email, edit if needed, click **Approve & Send**

## Configuration (`backend/.env`)

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_VISION_MODEL=llama3.2-vision
OLLAMA_TEXT_MODEL=llama3.2
OLLAMA_TIMEOUT=180

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
```

## Gmail SMTP setup

1. Enable 2-Factor Authentication on your Google account
2. Google Account → Security → App passwords
3. Create app password for "Mail"
4. Use as `SMTP_PASSWORD`

## License

MIT
