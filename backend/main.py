# Flow: check question -> load resume -> read history -> answer -> save turn.
# Python tools for text, logs, files, time, and shared memory.
import json
import logging
import os
from collections import OrderedDict  # Track recent chats.
from contextlib import asynccontextmanager  # Server cleanup.
from hashlib import sha256  # Check file changes.
from pathlib import Path  # Build file paths independently of the terminal folder.
from threading import Lock  # Guard shared memory.
from time import monotonic  # Measure time passed.
from uuid import UUID  # Check chat IDs.

# Packages for reading files, checking data, serving the API, and calling Groq.
from docx import Document  # Read Word paragraphs and tables.
from dotenv import load_dotenv  # Load local secrets without hardcoding credentials.
from fastapi import FastAPI, HTTPException, Request  # App, HTTP errors, request metadata.
from fastapi.middleware.cors import CORSMiddleware  # Browser cross-origin permissions.
from fastapi.responses import FileResponse, StreamingResponse  # Download files or send answer pieces.
from starlette.concurrency import iterate_in_threadpool  # Keep blocking SDK reads off the event loop.
from groq import Groq  # SDK client for the hosted language model.

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, constr, model_validator
from pypdf import PdfReader  # Extract selectable text from PDF pages; does not do OCR.
from pypdf.errors import PdfReadError  # Identify malformed PDF errors.

from starlette.middleware.body_limit import RequestBodyLimitMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address  # Read client IP.
from slowapi.errors import RateLimitExceeded

from groq import (
    APITimeoutError,
    APIConnectionError,
    APIStatusError,
    RateLimitError
)

# Log technical errors on the server; show short messages to visitors.
logger = logging.getLogger(__name__)

# A problem reading the resume file.
class ResumeExtractionError(Exception):
    pass

# The AI did not return usable JSON.
class ResumeParsingError(Exception):
    pass

# The JSON does not match our resume fields.
class ResumeValidationError(Exception):
    pass

# The AI answer is empty or unfinished.
class ChatResponseError(Exception):
    pass

# Use this file's folder, no matter where the server command is run.
BACKEND_DIR = Path(__file__).resolve().parent

load_dotenv(BACKEND_DIR / ".env")

# Read the key from the environment; stop startup if it is missing.
api_key = os.getenv("GROQ_API_KEY", "").strip()
if not api_key:
    raise RuntimeError("Set GROQ_API_KEY in backend/.env or the server environment")

# Reuse one client. Retrying can make the total wait longer than 30 seconds.
client = Groq(
    api_key=api_key,
    timeout=30.0,
    max_retries=1,
)

# Tokens are pieces of text. Parsing a whole resume needs a bigger limit.
model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

CHAT_MAX_TOKENS = 2048
RESUME_MAX_TOKENS = 8192

@asynccontextmanager
# Serve requests at yield, then close the client when the server stops.
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        client.close()

# Uvicorn runs this app; it holds our routes and settings.
app = FastAPI(lifespan=lifespan)

# Count requests by IP. Counts reset on restart and are not shared by workers.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Reject large request bodies before processing them (4 KiB maximum).
app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_size=4096
)

# Allow these browser origins. This is not a login or API access restriction.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://hiremeai-ai.vercel.app",
        "https://hiremeai-ai-portfolio.vercel.app",
    ],
    # Vercel creates a new URL on each deployment. Allow only this project/team.
    allow_origin_regex=r"https://hiremeai-ai-portfolio(?:-[a-z0-9-]+)?-keertan07s-projects\.vercel\.app",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# One job or internship. Reject unknown fields; missing values may be None.
class Experience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: constr(strip_whitespace=True, min_length=1, max_length=150) | None = None
    role: constr(strip_whitespace=True, min_length=1, max_length=150) | None = None
    duration: constr(strip_whitespace=True, min_length=1, max_length=100) | None = None
    description: constr(strip_whitespace=True, min_length=1, max_length=3000) | None = None

    skills_used: list[
        constr(strip_whitespace=True, min_length=1, max_length=60)
    ] = Field(default_factory=list, max_length=30)

# Resume facts: limits check the data shape, not whether facts are true.
# constr trims/limits text; Field sets limits; default_factory makes a fresh list.
class Resume(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: constr(strip_whitespace=True, min_length=1, max_length=120) | None = None
    email: EmailStr | None = None
    phone: constr(strip_whitespace=True, min_length=1, max_length=30) | None = None

    total_experience_years: float | None = Field(
        default=None,
        ge=0,
        le=60
    )

    skills: list[
        constr(strip_whitespace=True, min_length=1, max_length=60)
    ] = Field(default_factory=list, max_length=60)

    experiences: list[Experience] = Field(
        default_factory=list,
        max_length=30
    )

    education: list[
        constr(strip_whitespace=True, min_length=1, max_length=500)
    ] = Field(default_factory=list, max_length=20)

    projects: list[
        constr(strip_whitespace=True, min_length=1, max_length=1000)
    ] = Field(default_factory=list, max_length=50)

    certifications: list[
        constr(strip_whitespace=True, min_length=1, max_length=200)
    ] = Field(default_factory=list, max_length=30)

    # Reject an empty result after checking individual fields; zero years is valid.
    @model_validator(mode="after")
    def validate_resume(self):
        if not any([
            self.name,
            self.email,
            self.phone,
            self.total_experience_years is not None,
            self.skills,
            self.experiences,
            self.education,
            self.projects,
            self.certifications
        ]):
            raise ValueError("Empty resume data")

        return self

# Describe our expected fields for the parser prompt.
resume_schema = Resume.model_json_schema()

# Incoming JSON. Invalid UUIDs/questions return 422. The ID is not a login.
class ChatRequest(BaseModel):
    conversation_id: UUID
    question: constr(strip_whitespace=True, min_length=1, max_length=500)
    stream: bool = False  # Opt in to streaming; existing JSON callers still work.

# Outgoing JSON: the chat ID and a nonempty answer.
class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: constr(strip_whitespace=True, min_length=1)

# Resume rules first, then old turns, then the question.
# These rules guide the AI but cannot guarantee perfect facts.
def build_candidate_messages(question: str, resume: Resume, history: list[dict] | None = None):
    system_prompt = f"""
    You are an AI assistant representing a job candidate.
    Below is everything you know about the candidate.

    {resume.model_dump_json(indent=2)}

    Rules:
    1. Answer only using this information.
    2. Never hallucinate.
    3. If information is unavailable,
       say "I don't have enough information to answer that."
    4. Be professional.
    5. Answer as if HR is interviewing this candidate.
    6. Use conversation history to understand follow-up questions.
    7. Conversation history is context, not a source of new
       candidate facts. Verify factual answers against the resume.
    8. Use plain text and short paragraphs. Avoid Markdown formatting.
    """

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    if history:
        messages.extend(history)

    messages.append({
        "role": "user",
        "content": question
    })
    return messages

# Wait for a full JSON answer and check that it finished normally.
def ask_candidate(question: str, resume: Resume, history: list[dict] | None = None):
    messages = build_candidate_messages(question, resume, history)

    response = client.chat.completions.create(
        model=model, messages=messages, max_completion_tokens=CHAT_MAX_TOKENS
    )

    if not response.choices:
        raise ChatResponseError("Groq returned no response choices")

    if response.choices[0].finish_reason != "stop":
        raise ChatResponseError("Groq did not finish the answer normally")

    answer = response.choices[0].message.content

    if not isinstance(answer, str) or not answer.strip():
        raise ChatResponseError("Groq returned an empty or invalid answer")

    return answer.strip()

# Send text pieces as the AI writes. Save history only after completion.
def stream_candidate(payload: ChatRequest, resume: Resume, history: list[dict]):
    # JSON protects text newlines; a blank line marks the end of each event.
    def event(data):
        return f"data: {json.dumps(data)}\n\n"

    try:
        parts = []
        finish_reason = None

        # Close the provider connection when finished, stopped, or failed.
        with client.chat.completions.create(
            model=model,
            messages=build_candidate_messages(payload.question, resume, history),
            max_completion_tokens=CHAT_MAX_TOKENS,
            stream=True,
        ) as provider_stream:
            for chunk in provider_stream:
                if not chunk.choices:  # Usage/metadata chunks may contain no text.
                    continue
                choice = chunk.choices[0]
                text = choice.delta.content
                if text:
                    parts.append(text)
                    yield event({"type": "delta", "text": text})
                if choice.finish_reason is not None:
                    finish_reason = choice.finish_reason

        # A closed connection alone does not prove the answer is complete.
        answer = "".join(parts).strip()

        if finish_reason != "stop" or not answer:
            raise ChatResponseError("Answer stream was empty or incomplete")

        response = ChatResponse(conversation_id=payload.conversation_id, answer=answer)
        save_conversation_turn(payload.conversation_id, payload.question, response.answer)
        yield event({"type": "done", **response.model_dump(mode="json")})

    # Headers were sent already, so send streaming errors inside an event.
    except (APITimeoutError, APIConnectionError, APIStatusError, ChatResponseError) as exc:
        if isinstance(exc, APITimeoutError):
            detail = "AI service timed out. Please try again."
        elif isinstance(exc, RateLimitError):
            detail = "AI service is busy. Please try later."
        elif isinstance(exc, ChatResponseError):
            detail = "The answer was interrupted or incomplete. Please try again."
        else:
            detail = "AI service temporarily unavailable. Please try again."
        logger.warning("Chat stream failed: %s", type(exc).__name__)
        yield event({"type": "error", "detail": detail})
    except Exception:
        logger.exception("Unexpected chat stream failure")
        yield event({"type": "error", "detail": "Unable to finish the answer. Please try again."})

# Read blocking SDK results in a worker thread; close them on disconnect.
# A read already in progress may wait until the network timeout.
async def stream_events(payload: ChatRequest, resume: Resume, history: list[dict]):
    events = stream_candidate(payload, resume, history)
    try:
        async for event in iterate_in_threadpool(events):
            yield event
    finally:
        events.close()

# Convert document text to JSON, then check it with the Resume model.
def parse_resume(resume_text):
    system_prompt = f"""
    You are an expert resume parser.

    Extract information from the resume based on its meaning,
    not only based on exact section headings.

    Different resumes may use different headings.

    For example:
    - Experience
    - Professional Experience
    - Work History
    - Employment
    - Internships

    These may all contain relevant experience.

    Skills may also appear in the skills section, work experience,
    internships or projects.

    Return ONLY valid JSON matching this schema:

    {resume_schema}

    Important rules:

    1. Do not invent information.
    2. If a value is not available, return null.
    3. If a list has no information, return an empty list.
    4. Include internships inside experiences.
    5. Extract skills mentioned across the entire resume.
    """

    user_prompt = f"""
    Parse the following resume:

    {resume_text}
    """

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": user_prompt
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=RESUME_MAX_TOKENS,
        response_format={"type": "json_object"}
    )

    if not response.choices:
        raise ResumeParsingError("LLM returned no response choices")

    if response.choices[0].finish_reason == "length":
        raise ResumeParsingError("LLM resume response exceeded the token limit")

    raw_output = response.choices[0].message.content

    try:
        # Check JSON syntax before checking field values.
        data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ResumeParsingError(
            "LLM returned invalid JSON"
        ) from exc  # Preserve the original error as the cause for server debugging.

    if not isinstance(data, dict):
        raise ResumeParsingError(
            "LLM response must be a JSON object"
        )

    try:
        resume = Resume(**data)  # ** expands dictionary keys into model field values.
    except ValidationError as exc:
        raise ResumeValidationError(
            "Invalid resume schema"
        ) from exc

    return resume

# Limit document size and page count before sending text to the AI.
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MiB (commonly called 5 MB).
MAX_PDF_PAGES = 10

# Read selectable page text. Scanned images need OCR, which is not included.
def read_pdf(file_path: Path):
    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("PDF exceeds 5 MB limit")

    reader = PdfReader(file_path)

    if reader.is_encrypted:
        raise ValueError("Encrypted PDF is not supported")

    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError("PDF exceeds 10 pages")

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    if not text.strip():
        raise ValueError("No extractable text found in PDF")

    return text

# Read Word paragraphs and tables; images and text boxes are not read.
def read_docx(file_path: Path):
    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("DOCX exceeds 5 MB limit")

    document = Document(file_path)

    text_parts = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            text_parts.append(paragraph.text)

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text_parts.append(cell.text)

    text = "\n".join(text_parts)

    if not text.strip():
        raise ValueError("No extractable text found in DOCX")

    return text

# Choose a local-file reader by extension. This is not an upload API.
def extract_resume_text(file_path: Path):
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        return read_pdf(file_path)

    if extension == ".docx":
        return read_docx(file_path)

    raise ValueError("Unsupported resume format")

# Keep one parsed resume in memory; a content hash tells us when to refresh.
RESUME_PATH = BACKEND_DIR / "resume.pdf"
_resume_cache = {
    "version": None,
    "data": None
}
_resume_lock = Lock()  # Guard cache updates.
# Let one thread refresh the cache while other requests wait.
def get_cached_resume():
    with _resume_lock:
        try:
            with RESUME_PATH.open("rb") as resume_file:
                # One extra byte lets us detect an oversized file safely.
                contents = resume_file.read(MAX_FILE_SIZE + 1)
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise ResumeExtractionError(
                "Could not access resume file"
            ) from exc

        if len(contents) > MAX_FILE_SIZE:
            raise ResumeExtractionError("Resume exceeds 5 MB limit")

        # Detect edits even if the file size and date stay the same.
        version = sha256(contents).hexdigest()

        if _resume_cache["version"] != version:
            try:
                resume_text = extract_resume_text(RESUME_PATH)

            except FileNotFoundError:
                raise

            except (OSError, ValueError, PdfReadError) as exc:
                raise ResumeExtractionError(
                    "Resume extraction failed"
                ) from exc

            resume = parse_resume(resume_text)

            if not resume:
                raise ResumeValidationError(
                    "Resume parsing returned empty data"
                )

            # Replace the cache only after extraction and validation succeed.
            _resume_cache["data"] = resume
            _resume_cache["version"] = version

        return _resume_cache["data"]

# Keep 10 exchanges, expire idle chats after 30 minutes, and store at most 100.
MAX_HISTORY_MESSAGES = 20  # 10 user-assistant exchanges
CONVERSATION_TTL = 1800    # 30 minutes
MAX_CONVERSATIONS = 100

# Recent chats move to the end. Memory resets on restart; use one worker.
_conversation_store = OrderedDict()
_conversation_lock = Lock()

# Remove idle chats, find/create this chat, and return a copy of its messages.
def get_conversation_history(conversation_id: UUID):
    now = monotonic()
    conversation_id = str(conversation_id)

    with _conversation_lock:
        # monotonic measures time passed even when the system clock changes.
        expired = [
            cid for cid, session in _conversation_store.items()
            if now - session["last_access"] > CONVERSATION_TTL
        ]

        for cid in expired:
            del _conversation_store[cid]

        if conversation_id not in _conversation_store:
            _conversation_store[conversation_id] = {
                "messages": [],
                "last_access": now
            }

        session = _conversation_store[conversation_id]
        session["last_access"] = now

        _conversation_store.move_to_end(conversation_id)

        # Remove the oldest unused chat when the store is full.
        while len(_conversation_store) > MAX_CONVERSATIONS:
            _conversation_store.popitem(last=False)

        return list(session["messages"])

# Save a successful question/answer pair and trim older messages.
# The lock guards memory updates, not the entire AI request.
def save_conversation_turn(conversation_id: UUID, question: str, answer: str):
    conversation_id = str(conversation_id)

    with _conversation_lock:
        session = _conversation_store.get(conversation_id)

        # The chat may have been removed while its answer was being generated.
        if session is None:
            return

        session["messages"].extend([
            {
                "role": "user",
                "content": question
            },
            {
                "role": "assistant",
                "content": answer
            }
        ])

        session["messages"] = session["messages"][-MAX_HISTORY_MESSAGES:]

        session["last_access"] = monotonic()
        _conversation_store.move_to_end(conversation_id)

@app.get("/")
# Basic welcome route; /health checks the local resume file.
def home():
    return {
        "message" : "Ye home page hai"
    }

@app.get("/health")
# Check file access/size without an AI call. This does not test Groq.
def health():
    try:
        with RESUME_PATH.open("rb") as resume_file:
            size = os.fstat(resume_file.fileno()).st_size  # Size of the opened file.
    except OSError:
        raise HTTPException(status_code=503, detail="Resume temporarily unavailable")

    if size == 0 or size > MAX_FILE_SIZE:
        raise HTTPException(status_code=503, detail="Resume file is empty or too large")

    return {"status": "ok", "resume_cached": _resume_cache["data"] is not None}

@app.get("/resume", response_class=FileResponse)
# Download the same file the AI reads, rather than a separate frontend copy.
def download_resume():
    if not RESUME_PATH.is_file():
        raise HTTPException(status_code=503, detail="Resume temporarily unavailable")
    return FileResponse(
        RESUME_PATH,
        media_type="application/pdf",
        filename="Keertan-Resume.pdf",
        headers={"Cache-Control": "no-store"},  # Do not reuse an old downloaded PDF.
    )

# Both modes share validation, resume loading, and the five-per-minute limit.
@app.post("/chat", response_model=ChatResponse, responses={
    200: {"content": {"text/event-stream": {}}, "description": "JSON answer or streamed delta/done/error events"}
})
@limiter.limit("5/minute")
# FastAPI runs this blocking function in a worker thread.
# request supplies the IP; payload is the checked JSON body.
def chat(request: Request, payload: ChatRequest):
    try:
        try:
            # Parse only on the first request or when the file changes.
            resume = get_cached_resume()

        except FileNotFoundError:
            logger.error("Resume PDF not found")
            raise HTTPException(
                status_code=503,
                detail="Resume temporarily unavailable"
            )

        except ResumeExtractionError:
            logger.exception("Resume extraction failed")
            raise HTTPException(
                status_code=503,
                detail="Resume document could not be processed"
            )

        except ResumeParsingError:
            logger.exception("Resume parser returned invalid JSON")
            raise HTTPException(
                status_code=502,
                detail="Unable to process resume response"
            )

        except ResumeValidationError:
            logger.exception("Invalid parsed resume data")
            raise HTTPException(
                status_code=502,
                detail="Unable to process resume data"
            )

        # Load context before choosing a streamed or full JSON answer.
        history = get_conversation_history(payload.conversation_id)

        # Send pieces as they arrive; ask proxies not to buffer them.
        if payload.stream:
            return StreamingResponse(
                stream_events(payload, resume, history),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
            )

        answer = ask_candidate(
            payload.question,
            resume,
            history
        )

        # Check the complete answer before saving it to history.
        chat_response = ChatResponse(
            conversation_id=payload.conversation_id,
            answer=answer
        )

        save_conversation_turn(
            payload.conversation_id,
            payload.question,
            chat_response.answer
        )

        return chat_response

    # 502: bad AI reply; 503: unavailable service; 504: AI timeout.
    except ChatResponseError:
        logger.error("Groq returned an invalid chat response")
        raise HTTPException(
            status_code=502,
            detail="AI service returned an invalid response. Please try again."
        )

    except APITimeoutError:
        logger.warning("Groq API timeout")
        raise HTTPException(
            status_code=504,
            detail="AI service timed out. Please try again."
        )

    except RateLimitError:
        logger.warning("Groq API rate limit exceeded")
        raise HTTPException(
            status_code=503,
            detail="AI service is busy. Please try later."
        )

    except APIConnectionError:
        logger.warning("Unable to connect to Groq")
        raise HTTPException(
            status_code=503,
            detail="AI service temporarily unavailable"
        )

    except APIStatusError as exc:
        logger.error("Groq returned HTTP %s", exc.status_code)
        raise HTTPException(
            status_code=502,
            detail="AI service temporarily unavailable"
        )
