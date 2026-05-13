# Vaani: AI-Powered FNOL Voice Agent

Vaani is an enterprise-grade AI voice agent designed specifically for First Notice of Loss (FNOL) operations in the insurance industry. It handles inbound customer calls, collects critical incident data, verifies policies, and streams real-time analytics to a tactical command center dashboard.

## 🌟 Key Features

- **Conversational AI Pipeline**: Real-time integration with STT (Speech-to-Text), LLM (Large Language Model), and TTS (Text-to-Speech) engines.
- **Deterministic Guardrails**: Powered by a Finite State Machine (FSM) to ensure the AI follows strict compliance and data-collection protocols (e.g., Greeting -> Policy Verification -> Incident Capture).
- **Tactical Dashboard**: A Next.js frontend built for high-density data observation, inspired by premium developer tools.
- **Real-Time Observability**: WebSocket-driven live call monitoring, including transcript streaming and latency metrics.
- **Evaluation Suite**: Built-in evaluation framework to simulate calls and test LLM prompt updates.

---

## 🏗️ Architecture Overview

The system consists of two primary components:
1. **Frontend (Next.js)**: The tactical operator dashboard.
2. **Backend (FastAPI)**: The real-time AI pipeline and WebSocket server.

For deep dives into the system design, see the [Documentation Directory](./docs).
- [Architecture & Design](./docs/ARCHITECTURE.md)
- [API & WebSocket Protocol](./docs/API_AND_WEBSOCKETS.md)
- [AI & Prompt Strategy](./docs/AI_AND_PROMPTING.md)
- [Deployment Guide](./docs/DEPLOYMENT.md)

---

## 🚀 Quickstart

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- Poetry (Python package manager)
- API Keys for your preferred LLM/STT/TTS providers (e.g., OpenAI, Deepgram, ElevenLabs)

### 1. Environment Setup

Create a `.env` file in the root directory (or use the provided `.env.example`):

```env
# Backend / AI Providers
OPENAI_API_KEY=your_openai_key
DEEPGRAM_API_KEY=your_deepgram_key
ELEVENLABS_API_KEY=your_elevenlabs_key

# Database
DATABASE_URL=sqlite:///./vaani.db

# Frontend
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

### 2. Run the Backend (FastAPI)

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```
*The API will be available at `http://localhost:8000` with Swagger docs at `http://localhost:8000/docs`.*

### 3. Run the Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```
*The command center dashboard will be available at `http://localhost:3000`.*

---

## 🧪 Development Workflow

Currently, the frontend features a **Mock Data Interceptor** to allow UI development without requiring the backend to be running. 
To disable mock data and connect to the live backend, open `frontend/src/lib/api.ts` and remove the early return block labeled `MOCK DATA INTERCEPTOR`.
