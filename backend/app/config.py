from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Sarvam AI
    SARVAM_API_KEY: str = ""
    SARVAM_STT_MODEL: str = "saarika:v2.5"
    SARVAM_TTS_MODEL: str = "bulbul:v2"
    SARVAM_TTS_SPEAKER: str = "meera"

    # LLM
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"

    # Langfuse
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"

    # Auth
    JWT_SECRET_KEY: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"

    # App
    DATABASE_URL: str = "sqlite+aiosqlite:///./vaani.db"
    AUDIO_STORAGE_DIR: str = "./audio_artifacts"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    ENVIRONMENT: str = "development"

    # Pipeline tuning
    ACTIVE_PROMPT_VERSION: str = "v1"
    MAX_CONCURRENT_CALLS: int = 10
    STT_BUFFER_MS: int = 300
    VAD_THRESHOLD: float = 0.5
    LANGUAGE_DETECTION_TURNS: int = 1

    # Circuit breaker
    CB_ERROR_THRESHOLD: int = 3
    CB_COOLDOWN_SECONDS: int = 60
    CB_DISABLE_THRESHOLD: int = 3
    CB_RECOVERY_SECONDS: int = 600  # DISABLED → COOLING_DOWN self-recovery after 10 min

    # Rate limiting
    RATE_LIMIT_API: str = "100/minute"
    RATE_LIMIT_CALLS: str = "30/minute"
    RATE_LIMIT_AUTH: str = "10/minute"

    # Webhooks
    FNOL_WEBHOOK_URL: str = ""

    # Frontend
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"
    NEXT_PUBLIC_WS_URL: str = "ws://localhost:8000"


settings = Settings()
