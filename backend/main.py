import json
import os
from pathlib import Path

## basic imports
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel , constr ## for constraining the length of the question
from pypdf import PdfReader

## for limiting request body size
from starlette.middleware.body_limit import RequestBodyLimitMiddleware

##for rate limiting
from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

## for caching
from pathlib import Path
from threading import Lock

## for error handling of various exceptions that may occur during the process of reading and parsing the resume, as well as interacting with the Groq API
import json
import logging
from fastapi import HTTPException, Request
from pydantic import ValidationError
from groq import (
    APITimeoutError,
    APIConnectionError,
    APIStatusError,
    RateLimitError
)
logger = logging.getLogger(__name__)

##resume schema validation
from pydantic import Field, EmailStr, model_validator

### for ordered dict to maintain the order of the fields in the resume schema
from collections import OrderedDict
from time import monotonic
from uuid import UUID

##for custom exceptions handling below
class ResumeExtractionError(Exception):
    pass
class ResumeParsingError(Exception):
    pass
class ResumeValidationError(Exception):
    pass


load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

model = "openai/gpt-oss-120b"
app=FastAPI()

##for rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    RequestBodyLimitMiddleware,
    max_body_size=4096
)

## chnages made in cors middleware to allow only specific origins for security reasons
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://hiremeai-ai.vercel.app"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)



#parsing resume
class Experience(BaseModel):
    company: str | None = None
    role: str | None = None
    duration: str | None = None
    description: str | None = None
    skills_used: list[str] = Field(default_factory=list)

class Resume(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    total_experience_years: float | None = Field(default=None, ge=0)
    skills: list[str] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_resume(self):
        if not any([
            self.name, self.email, self.phone,
            self.total_experience_years is not None,
            self.skills, self.experiences,
            self.education, self.projects, self.certifications
        ]):
            raise ValueError("Empty resume data")
        return self


resume_schema = Resume.model_json_schema()


class ChatRequest(BaseModel):
    conversation_id: UUID
    question: constr(strip_whitespace=True, min_length=1, max_length=500)



def ask_candidate(question: str,resume: Resume,history: list[dict] | None = None):
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
    """

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]
    # Add previous conversation messages
    if history:
        messages.extend(history)
    # Add current question
    messages.append({
        "role": "user",
        "content": question
    })
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content


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
        response_format={"type": "json_object"}
    )

    raw_output = response.choices[0].message.content

    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ResumeParsingError(
            "LLM returned invalid JSON"
        ) from exc

    if not isinstance(data, dict):
        raise ResumeParsingError(
            "LLM response must be a JSON object"
        )

    try:
        resume = Resume(**data)
    except ValidationError as exc:
        raise ResumeValidationError(
            "Invalid resume schema"
        ) from exc

    return resume




## functions to read pdf and docx files
from docx import Document
from pypdf.errors import PdfReadError

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_PDF_PAGES = 10


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


def extract_resume_text(file_path: Path):
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        return read_pdf(file_path)

    if extension == ".docx":
        return read_docx(file_path)

    raise ValueError("Unsupported resume format")





## caching the resume to avoid re-parsing it on every request
##it will parse resume only if the file has changed (based on modification time and size) if not changed it will return the cached resume
RESUME_PATH = Path(__file__).resolve().parent / "resume.pdf"
_resume_cache = {
    "version": None,
    "data": None
}
_resume_lock = Lock()##lock to ensure thread safety when accessing the cache
def get_cached_resume():
    with _resume_lock:

        try:
            stat = RESUME_PATH.stat()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise ResumeExtractionError(
                "Could not access resume file"
            ) from exc

        version = (stat.st_mtime_ns, stat.st_size)

        if _resume_cache["version"] != version:

            # Extract text from the resume document
            try:
                resume_text = extract_resume_text(RESUME_PATH)

            except FileNotFoundError:
                raise

            except (OSError, ValueError, PdfReadError) as exc:
                raise ResumeExtractionError(
                    "Resume extraction failed"
                ) from exc

            # Parse and validate extracted resume data
            resume = parse_resume(resume_text)

            if not resume:
                raise ResumeValidationError(
                    "Resume parsing returned empty data"
                )

            # Update cache only after successful processing
            _resume_cache["data"] = resume
            _resume_cache["version"] = version

        return _resume_cache["data"]


# Conversation memory configuration
MAX_HISTORY_MESSAGES = 20  # 10 user-assistant exchanges
CONVERSATION_TTL = 1800    # 30 minutes
MAX_CONVERSATIONS = 100

_conversation_store = OrderedDict()
_conversation_lock = Lock()


def get_conversation_history(conversation_id: UUID):

    now = monotonic()
    conversation_id = str(conversation_id)

    with _conversation_lock:

        # Remove expired conversations
        expired = [
            cid for cid, session in _conversation_store.items()
            if now - session["last_access"] > CONVERSATION_TTL
        ]

        for cid in expired:
            del _conversation_store[cid]

        # Create a new conversation if it doesn't exist
        if conversation_id not in _conversation_store:
            _conversation_store[conversation_id] = {
                "messages": [],
                "last_access": now
            }

        session = _conversation_store[conversation_id]
        session["last_access"] = now

        _conversation_store.move_to_end(conversation_id)

        # Limit total active conversations
        while len(_conversation_store) > MAX_CONVERSATIONS:
            _conversation_store.popitem(last=False)

        return list(session["messages"])


def save_conversation_turn(conversation_id: UUID, question: str, answer: str):

    conversation_id = str(conversation_id)

    with _conversation_lock:

        session = _conversation_store.get(conversation_id)

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

        # Keep only the latest messages
        session["messages"] = session["messages"][-MAX_HISTORY_MESSAGES:]

        session["last_access"] = monotonic()
        _conversation_store.move_to_end(conversation_id)



@app.get("/")
def home():
    return {
        "message" : "Ye home page hai"
    }


# @app.post("/chat")
# @limiter.limit("5/minute")
# def chat(request: Request, payload: ChatRequest):##adding rate limiter
#     resume = get_cached_resume()
#     answer = ask_candidate(payload.question, resume)
#     return {
#         "answer": answer
#     }


##updated (includes error handling for various exceptions that may occur during the process of reading and parsing the resume, as well as interacting with the Groq API)
@app.post("/chat")
@limiter.limit("5/minute")
def chat(request: Request, payload: ChatRequest):

    try:
        # Retrieve cached resume
        try:
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
                status_code=500,
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

        # Retrieve previous conversation history
        history = get_conversation_history(payload.conversation_id)

        # Generate response using conversation context
        answer = ask_candidate(
            payload.question,
            resume,
            history
        )

        # Save current question and response
        save_conversation_turn(
            payload.conversation_id,
            payload.question,
            answer
        )

        return {
            "conversation_id": str(payload.conversation_id),
            "answer": answer
        }

    # Groq API error handling
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


