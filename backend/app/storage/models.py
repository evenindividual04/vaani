from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class CallRecord(Base):
    __tablename__ = "call_records"

    call_id: Mapped[str] = mapped_column(String, primary_key=True,
                                          default=lambda: str(uuid.uuid4()))
    channel: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(10))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), default="active")
    prompt_version: Mapped[str] = mapped_column(String(20))
    twilio_call_sid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    turns: Mapped[list["ConversationTurn"]] = relationship(back_populates="call",
                                                            cascade="all, delete-orphan")
    fnol_record: Mapped[Optional["FNOLRecord"]] = relationship(back_populates="call",
                                                                uselist=False)
    pipeline_metrics: Mapped[list["TurnMetrics"]] = relationship(back_populates="call",
                                                                   cascade="all, delete-orphan")
    audio_artifact: Mapped[Optional["AudioArtifact"]] = relationship(back_populates="call",
                                                                       uselist=False)


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_records.call_id"))
    turn_index: Mapped[int] = mapped_column()
    speaker: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(10))
    timestamp_ms: Mapped[int] = mapped_column()
    fsm_state: Mapped[str] = mapped_column(String(30))

    call: Mapped["CallRecord"] = relationship(back_populates="turns")


class FNOLRecord(Base):
    __tablename__ = "fnol_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_records.call_id"), unique=True)
    policy_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    incident_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    incident_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    incident_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    injuries_reported: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    injury_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vehicle_damage: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    damage_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    third_party_involved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    callback_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="hi-IN")
    extraction_confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    completeness_score: Mapped[float] = mapped_column(Float, default=0.0)
    extracted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    call: Mapped["CallRecord"] = relationship(back_populates="fnol_record")


class TurnMetrics(Base):
    __tablename__ = "turn_metrics"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_records.call_id"))
    turn_index: Mapped[int] = mapped_column()
    stt_ms: Mapped[float] = mapped_column(Float, default=0.0)
    llm_ms: Mapped[float] = mapped_column(Float, default=0.0)
    llm_ttft_ms: Mapped[float] = mapped_column(Float, default=0.0)
    tts_ms: Mapped[float] = mapped_column(Float, default=0.0)
    total_ms: Mapped[float] = mapped_column(Float, default=0.0)
    stt_provider: Mapped[str] = mapped_column(String(30), default="sarvam")
    llm_provider: Mapped[str] = mapped_column(String(30), default="groq")
    tts_provider: Mapped[str] = mapped_column(String(30), default="sarvam")
    fallback_triggered: Mapped[bool] = mapped_column(Boolean, default=False)

    call: Mapped["CallRecord"] = relationship(back_populates="pipeline_metrics")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    version_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    templates: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    eval_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                         default=lambda: str(uuid.uuid4()))
    prompt_version_id: Mapped[str] = mapped_column(String(20))
    baseline_version_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    scenario_results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    resource_type: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class AudioArtifact(Base):
    __tablename__ = "audio_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    call_id: Mapped[str] = mapped_column(ForeignKey("call_records.call_id"), unique=True)
    file_path: Mapped[str] = mapped_column(Text)
    file_size_bytes: Mapped[int] = mapped_column()
    duration_seconds: Mapped[float] = mapped_column(Float)

    call: Mapped["CallRecord"] = relationship(back_populates="audio_artifact")
