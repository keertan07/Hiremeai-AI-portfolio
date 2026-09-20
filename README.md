 Keertan's AI Portfolio 🚀
Welcome to **Keertan's AI Portfolio**! Instead of a traditional static website, this portfolio uses an interactive, ChatGPT-style AI chatbot to answer questions about my experience, skills, projects, and education.
## ✨ Features
- **ChatGPT-Style Interface**: A modern, interactive UI featuring a collapsible sidebar, chat history, and an animated message interface.
- **Dark & Light Mode**: Seamless theme toggling using CSS variables.
- **AI-Powered Backend**: Uses FastAPI and the Groq API to parse my resume and dynamically answer recruiter questions without hallucinating.
- **Direct Resume Download**: Recruiters can instantly download my PDF resume directly from the sidebar.
## 🛠️ Tech Stack
- **Frontend**: React.js (Vite), Vanilla CSS
- **Backend**: Python, FastAPI
- **LLM Engine**: Groq API
---
## 💻 Running Locally
To run this project on your local machine, you will need to start both the backend and frontend servers.
### 1. Backend Setup (FastAPI)
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create a `.env` file (you can copy `.env.example`) and add your Groq API key:
   ```ini
   GROQ_API_KEY=your_groq_api_key_here
   ```
3. Run the backend server using Uvicorn:
   ```bash
   uv run uvicorn main:app --reload
   ```
   *The backend will run on `http://127.0.0.1:8000`.*
### 2. Frontend Setup (React/Vite)
1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install the dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   *The frontend will run on `http://localhost:5173`. Open this URL in your browser.*
