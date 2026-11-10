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

1. Navigate to the backend directory:
   ```bash
   cd backend
