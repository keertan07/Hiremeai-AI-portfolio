# Keertan's AI Portfolio 🚀

Welcome to my AI-powered portfolio! Instead of a traditional static website, I have built an interactive, ChatGPT-style AI assistant to represent me. Recruiters, engineering managers, and visitors can chat directly with my AI to learn about my professional experience, technical skills, education, and past projects.

## ✨ Key Features
- **ChatGPT-Style Interface**: A modern, interactive UI featuring a collapsible sidebar, historical chat sessions, and an animated message interface.
- **Dark & Light Mode**: Seamless theme toggling using advanced CSS variables.
- **AI-Powered Backend**: Uses FastAPI and the Groq API to parse my resume dynamically. It acts as an intelligent agent representing my professional background.
- **Strict Prompt Engineering**: The LLM is strictly instructed to only answer using information from my resume and never hallucinate capabilities.
- **Direct Resume Download**: Visitors can instantly download my PDF resume directly from the sidebar.

## 🛠️ Technology Stack

### Frontend
- **Framework**: React.js (Bootstrapped with Vite for lightning-fast HMR)
- **Styling**: Vanilla CSS with custom CSS variables for complex theming and keyframe animations.
- **Deployment**: Vercel

### Backend
- **Framework**: Python / FastAPI (High performance, async web framework)
- **LLM Engine**: Groq API (Running `openai/gpt-oss-120b` for ultra-fast, intelligent responses)
- **PDF Parsing**: `pypdf` (Extracts textual context directly from my resume)
- **Data Validation**: Pydantic models to strictly structure the parsed resume data.
- **Deployment**: Render

---

## 💻 Running the Project Locally

To run this project on your local machine, you will need to start both the FastAPI backend and the Vite frontend servers.

### 1. Backend Setup (FastAPI)
The backend acts as the bridge to the Groq API and handles parsing the resume context.

From the project root, install the locked Python dependencies (Python 3.13+ and uv):

```powershell
uv sync --locked
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

If `backend/.env` already exists, keep it. Set `GROQ_API_KEY` in that file.
`GROQ_MODEL` is optional. Server environment variables take precedence over the file.
Keep the resume at `backend/resume.pdf`.

Start the backend from the project root:

```powershell
uv run uvicorn backend.main:app --reload
```

API documentation: http://127.0.0.1:8000/docs
Local health check: http://127.0.0.1:8000/health
The health check verifies that the resume file is readable, nonempty, and within
the size limit. It does not parse the document or check Groq availability.

### 2. Frontend Setup

In another PowerShell terminal, from the project root:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Development uses the backend at http://127.0.0.1:8000.
Deployed builds use `VITE_API_URL`, or the project's Render backend when that
setting is missing. After changing a Vercel environment variable, redeploy the frontend.
For this project, set Vercel's `VITE_API_URL` to
`https://hiremeai-ai-portfolio.onrender.com/chat`. Chat uses POST `/chat`;
POST to the backend home page returns "Method Not Allowed".
The backend allows this project's public and preview Vercel addresses. If you
rename the Vercel project/team, update its allowed origins in `backend/main.py`
and redeploy the backend on Render too.

### Backend checks

```powershell
uv run python -m unittest discover -s tests -v
```

These checks mock Groq and do not send the resume to an AI provider.
Conversation history and request limits are stored in memory: use one backend
worker for this setup. Restarting the server clears conversation history and limits.

### Streaming answers

The frontend requests streamed answers from the existing `/chat` endpoint and
displays incoming text immediately. Use the square Stop button to cancel a response.
API callers can send `stream: true` for server-sent events; omitting it keeps the
existing JSON response. The first request still waits for uncached resume parsing.

Run the browser stream-parser checks with `npm test` from `frontend`.
See [STREAMING_REPORT.md](STREAMING_REPORT.md) for the protocol, changes, and limits.
