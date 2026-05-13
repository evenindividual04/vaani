# Deployment & Infrastructure

Deploying the Vaani platform requires managing a real-time Python backend and a static/SSR Next.js frontend. 

## Infrastructure Recommendations

### 1. The Frontend (Next.js)
**Platform: Vercel**
- The Next.js Command Center is optimized for edge delivery.
- Vercel provides out-of-the-box support for Next.js 15 App Router.
- **Environment Variables**: Ensure `NEXT_PUBLIC_WS_URL` and `NEXT_PUBLIC_API_URL` point to the production backend URLs (e.g., `wss://api.vaani.com/ws`).

### 2. The Backend (FastAPI + WebSockets)
**Platform: Render / AWS ECS / DigitalOcean App Platform**
- Because the backend manages long-lived WebSocket connections, serverless functions (like AWS Lambda) are generally **not suitable** without an API Gateway WebSocket wrapper.
- A long-running containerized environment (Docker) is highly recommended.
- **Scaling**: If deploying multiple backend instances, you must use a Redis pub/sub backplane to manage WebSocket connections across instances.

## 🐳 Docker Deployment

The repository includes (or should include) a `Dockerfile` for the backend.

### Backend Dockerfile (Example)
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev

COPY ./app ./app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🔒 Security & Secrets

Production deployments must secure several sensitive keys:
1. **LLM Provider Keys** (OpenAI, Anthropic): Never expose these to the frontend. All LLM calls must route through the FastAPI backend.
2. **Audio Provider Keys** (Deepgram, ElevenLabs): Keep these secured in the backend.
3. **Database Credentials**: Secure the PostgreSQL/SQLite URL.

### CORS & Origin Configuration
Ensure the FastAPI backend explicitly allows CORS for the production frontend domain to prevent unauthorized WebSocket connections or API calls.

```python
# backend/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-vercel-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📈 Monitoring in Production

- **Frontend Latency**: Monitor Vercel Web Vitals.
- **AI Latency**: The backend emits metrics for `stt_ms`, `llm_ms`, and `tts_ms`. Route these metrics to Datadog or Prometheus to set alerts if LLM generation time spikes above an acceptable threshold (e.g., 2000ms), as this directly impacts the caller's experience.
