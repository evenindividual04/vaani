# System Architecture & Design

Vaani is built with a decoupled architecture, separating the real-time AI inference pipeline from the tactical observation frontend. 

## High-Level Architecture Diagram

```mermaid
graph TD
    %% Users
    Customer([Caller / Customer])
    Operator([FNOL Operator])

    %% Frontend
    subgraph Frontend [Next.js Command Center]
        Dashboard[Live Dashboard]
        Zustand[Zustand State Store]
        Dashboard <--> Zustand
    end

    %% Backend
    subgraph Backend [FastAPI Backend]
        REST[REST API]
        WS[WebSocket Manager]
        FSM[Finite State Machine]
        DB[(PostgreSQL/SQLite)]
        
        REST <--> DB
    end

    %% AI Pipeline
    subgraph Pipeline [AI Inference Pipeline]
        STT[Speech-to-Text]
        LLM[Large Language Model]
        TTS[Text-to-Speech]
    end

    %% Connections
    Operator <-->|HTTP/WS| Frontend
    Customer <-->|Twilio / WebRTC| WS
    
    Frontend <-->|REST| REST
    Frontend <-->|WebSocket| WS
    
    WS <--> FSM
    FSM <--> Pipeline
```

## Core Components

### 1. The Finite State Machine (FSM)
The core logic of the Vaani agent is not a single sprawling LLM prompt, but rather a deterministic Finite State Machine. This ensures the AI follows strict insurance compliance protocols and doesn't hallucinate outside of its current objective.

**States:**
1. `GREETING`: Identify the caller and purpose.
2. `POLICY_VERIFY`: Collect policy number and validate.
3. `INCIDENT_CAPTURE`: Determine if it's auto, home, or medical.
4. `DETAILS_CAPTURE`: Gather specific details (injuries, location, damage).
5. `CONTACT_VERIFY`: Confirm callback number.
6. `SUMMARY`: Summarize and conclude the call.

### 2. The AI Pipeline (Backend)
The backend pipeline operates asynchronously to minimize latency. 
- **STT (Speech-to-Text)**: Streams audio from the caller and converts to text (e.g., via Deepgram).
- **LLM (Reasoning)**: The LLM acts as the "brain". It takes the STT output, the current FSM state instructions, and the conversation history to generate a response AND extract structured JSON data (FNOL record).
- **TTS (Text-to-Speech)**: Streams the LLM text output back to the caller as human-like audio (e.g., via ElevenLabs).

### 3. Real-Time Observability (Frontend)
The Next.js frontend uses a Zustand store to manage real-time state. It connects to the FastAPI backend via WebSockets.
- Every time the Pipeline processes a turn (User speaks -> Agent replies), the backend broadcasts a JSON payload.
- The Zustand store updates the `liveCalls` dictionary.
- The React components (like `LiveCallPanel` and `CallCard`) re-render instantly, allowing operators to monitor the FSM state, extracted variables, and transcription latency in real-time.
