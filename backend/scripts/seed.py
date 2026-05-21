"""
Seed the database with realistic demo data.

Usage (from backend/):
    python scripts/seed.py

Creates 8 calls across all channels and outcomes, with conversation turns,
FNOL records, pipeline metrics, and a v1 prompt version — enough to make
the dashboard look alive for a demo.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow running from repo root or from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./vaani.db")
os.environ.setdefault("SARVAM_API_KEY", "seed-placeholder")
os.environ.setdefault("GROQ_API_KEY", "seed-placeholder")
os.environ.setdefault("GOOGLE_API_KEY", "seed-placeholder")
os.environ.setdefault("JWT_SECRET_KEY", "seed-placeholder")
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_PASSWORD", "admin")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.storage.models import (
    Base,
    CallRecord,
    ConversationTurn,
    FNOLRecord,
    PromptVersion,
    TurnMetrics,
)

NOW = datetime.utcnow()


CALLS = [
    {
        "call_id": "demo-001",
        "channel": "web",
        "language": "hi-IN",
        "started_at": NOW - timedelta(minutes=3),
        "ended_at": NOW - timedelta(minutes=1),
        "duration_seconds": 127,
        "outcome": "complete",
        "prompt_version": "v1",
        "fnol": {
            "policy_number": "SBI-2024-789456",
            "incident_type": "accident",
            "incident_date": "2024-03-15",
            "incident_location": "Mumbai-Pune Expressway, near Khopoli",
            "injuries_reported": True,
            "injury_description": "Minor whiplash, front passenger",
            "vehicle_damage": True,
            "damage_description": "Front bumper and bonnet damage",
            "third_party_involved": True,
            "callback_number": "9876543210",
            "preferred_language": "hi-IN",
            "completeness_score": 0.92,
            "extraction_confidence": {
                "policy_number": 0.98, "incident_type": 0.95, "incident_date": 0.88,
                "incident_location": 0.91, "injuries_reported": 0.99,
                "vehicle_damage": 0.99, "callback_number": 0.97,
            },
        },
        "turns": [
            ("agent", "नमस्ते! मैं वाणी हूं। आपकी पॉलिसी नंबर बताइए।", "POLICY_VERIFICATION"),
            ("user",  "मेरी पॉलिसी नंबर है SBI-2024-789456", "POLICY_VERIFICATION"),
            ("agent", "धन्यवाद। क्या हुआ? घटना कब और कहाँ हुई?", "INCIDENT_CAPTURE"),
            ("user",  "कल रात मुंबई-पुणे एक्सप्रेसवे पर एक्सीडेंट हुआ। सामने की गाड़ी ने अचानक ब्रेक लगाए।", "INCIDENT_CAPTURE"),
            ("agent", "समझ गया। क्या किसी को चोट आई?", "DETAIL_COLLECTION"),
            ("user",  "हाँ, सामने बैठे यात्री को गर्दन में हल्की चोट है।", "DETAIL_COLLECTION"),
            ("agent", "ठीक है। आपका कॉलबैक नंबर क्या है?", "CALLBACK_COLLECTION"),
            ("user",  "9876543210", "CALLBACK_COLLECTION"),
            ("agent", "आपकी FNOL दर्ज हो गई। हमारा प्रतिनिधि 24 घंटे में संपर्क करेगा।", "CLOSED"),
        ],
        "metrics": [
            (310, 820, 145, 680),
            (290, 760, 138, 640),
            (325, 890, 152, 710),
            (305, 840, 141, 695),
        ],
    },
    {
        "call_id": "demo-002",
        "channel": "phone",
        "language": "en-IN",
        "started_at": NOW - timedelta(minutes=18),
        "ended_at": NOW - timedelta(minutes=15),
        "duration_seconds": 198,
        "outcome": "complete",
        "prompt_version": "v1",
        "fnol": {
            "policy_number": "HDFC-MH-2023-441122",
            "incident_type": "theft",
            "incident_date": "2024-03-14",
            "incident_location": "Bandra West, Mumbai",
            "injuries_reported": False,
            "vehicle_damage": None,
            "third_party_involved": False,
            "callback_number": "8800112233",
            "preferred_language": "en-IN",
            "completeness_score": 0.85,
            "extraction_confidence": {
                "policy_number": 0.96, "incident_type": 0.93, "incident_date": 0.90,
                "incident_location": 0.87, "injuries_reported": 0.99,
                "callback_number": 0.95,
            },
        },
        "turns": [
            ("agent", "Hello, this is Vaani. Please share your policy number.", "POLICY_VERIFICATION"),
            ("user",  "HDFC-MH-2023-441122", "POLICY_VERIFICATION"),
            ("agent", "Thank you. What happened? Please describe the incident.", "INCIDENT_CAPTURE"),
            ("user",  "My car was stolen last night from the Bandra parking lot.", "INCIDENT_CAPTURE"),
            ("agent", "I'm sorry to hear that. Was anyone injured?", "DETAIL_COLLECTION"),
            ("user",  "No, thankfully. I discovered it missing this morning.", "DETAIL_COLLECTION"),
            ("agent", "Understood. What is the best number to reach you?", "CALLBACK_COLLECTION"),
            ("user",  "8800112233", "CALLBACK_COLLECTION"),
            ("agent", "Your theft claim has been registered. An investigator will contact you within 24 hours.", "CLOSED"),
        ],
        "metrics": [
            (285, 790, 132, 620),
            (298, 815, 140, 655),
            (312, 860, 148, 690),
            (275, 780, 128, 610),
        ],
    },
    {
        "call_id": "demo-003",
        "channel": "web",
        "language": "hi-IN",
        "started_at": NOW - timedelta(hours=1, minutes=12),
        "ended_at": NOW - timedelta(hours=1, minutes=8),
        "duration_seconds": 243,
        "outcome": "complete",
        "prompt_version": "v1",
        "fnol": {
            "policy_number": "ICICI-DL-2024-887733",
            "incident_type": "flood",
            "incident_date": "2024-03-13",
            "incident_location": "Dwarka Sector 12, Delhi",
            "injuries_reported": False,
            "vehicle_damage": True,
            "damage_description": "Engine seized due to waterlogging",
            "third_party_involved": False,
            "callback_number": "9911223344",
            "preferred_language": "hi-IN",
            "completeness_score": 0.88,
            "extraction_confidence": {
                "policy_number": 0.97, "incident_type": 0.89, "incident_date": 0.85,
                "incident_location": 0.92, "vehicle_damage": 0.96, "callback_number": 0.98,
            },
        },
        "turns": [
            ("agent", "नमस्ते! पॉलिसी नंबर बताइए।", "POLICY_VERIFICATION"),
            ("user",  "ICICI-DL-2024-887733", "POLICY_VERIFICATION"),
            ("agent", "क्या हुआ?", "INCIDENT_CAPTURE"),
            ("user",  "बाढ़ में गाड़ी डूब गई, इंजन खराब हो गया है।", "INCIDENT_CAPTURE"),
            ("agent", "कहाँ और कब?", "DETAIL_COLLECTION"),
            ("user",  "द्वारका सेक्टर 12 में, कल रात से पानी भरा था।", "DETAIL_COLLECTION"),
            ("agent", "कॉलबैक नंबर दीजिए।", "CALLBACK_COLLECTION"),
            ("user",  "9911223344", "CALLBACK_COLLECTION"),
            ("agent", "क्लेम दर्ज हो गया है।", "CLOSED"),
        ],
        "metrics": [
            (318, 875, 155, 705),
            (302, 845, 143, 675),
        ],
    },
    {
        "call_id": "demo-004",
        "channel": "phone",
        "language": "en-IN",
        "started_at": NOW - timedelta(hours=2, minutes=5),
        "ended_at": NOW - timedelta(hours=2),
        "duration_seconds": 305,
        "outcome": "complete",
        "prompt_version": "v1",
        "fnol": {
            "policy_number": "BAJAJ-KA-2023-556677",
            "incident_type": "fire",
            "incident_date": "2024-03-12",
            "incident_location": "Koramangala, Bengaluru",
            "injuries_reported": False,
            "vehicle_damage": True,
            "damage_description": "Total loss — engine compartment fire",
            "third_party_involved": False,
            "callback_number": "7700334455",
            "preferred_language": "en-IN",
            "completeness_score": 0.94,
            "extraction_confidence": {
                "policy_number": 0.99, "incident_type": 0.97, "incident_date": 0.91,
                "incident_location": 0.88, "vehicle_damage": 0.99, "callback_number": 0.96,
            },
        },
        "turns": [
            ("agent", "Hello, this is Vaani. Policy number please.", "POLICY_VERIFICATION"),
            ("user",  "BAJAJ-KA-2023-556677", "POLICY_VERIFICATION"),
            ("agent", "What is the nature of the incident?", "INCIDENT_CAPTURE"),
            ("user",  "My car caught fire while I was driving. Total loss.", "INCIDENT_CAPTURE"),
            ("agent", "Were you or anyone else injured?", "DETAIL_COLLECTION"),
            ("user",  "No, I managed to get out in time.", "DETAIL_COLLECTION"),
            ("agent", "Your callback number?", "CALLBACK_COLLECTION"),
            ("user",  "7700334455", "CALLBACK_COLLECTION"),
            ("agent", "Claim registered. Our assessor will contact you within 4 hours for a total-loss vehicle.", "CLOSED"),
        ],
        "metrics": [
            (295, 810, 136, 640),
            (308, 855, 149, 685),
            (285, 795, 131, 625),
        ],
    },
    {
        "call_id": "demo-005",
        "channel": "whatsapp",
        "language": "hi-IN",
        "started_at": NOW - timedelta(hours=3, minutes=30),
        "ended_at": NOW - timedelta(hours=3, minutes=25),
        "duration_seconds": 312,
        "outcome": "partial",
        "prompt_version": "v1",
        "fnol": {
            "policy_number": "LIC-MH-2022-334455",
            "incident_type": "accident",
            "incident_date": None,
            "incident_location": "Pune",
            "injuries_reported": True,
            "vehicle_damage": True,
            "third_party_involved": None,
            "callback_number": None,
            "preferred_language": "hi-IN",
            "completeness_score": 0.52,
            "extraction_confidence": {
                "policy_number": 0.94, "incident_type": 0.88,
                "incident_location": 0.75, "injuries_reported": 0.91,
            },
        },
        "turns": [
            ("agent", "नमस्ते! पॉलिसी नंबर बताइए।", "POLICY_VERIFICATION"),
            ("user",  "LIC-MH-2022-334455", "POLICY_VERIFICATION"),
            ("agent", "घटना का विवरण दीजिए।", "INCIDENT_CAPTURE"),
            ("user",  "पुणे में एक्सीडेंट हुआ था", "INCIDENT_CAPTURE"),
            ("agent", "कब हुआ था?", "DETAIL_COLLECTION"),
            ("user",  "अभी बात नहीं कर सकता, बाद में कॉल करूंगा", "DETAIL_COLLECTION"),
        ],
        "metrics": [
            (320, 880, 156, 715),
            (299, 832, 144, 668),
        ],
    },
    {
        "call_id": "demo-006",
        "channel": "web",
        "language": "en-IN",
        "started_at": NOW - timedelta(hours=5),
        "ended_at": NOW - timedelta(hours=4, minutes=58),
        "duration_seconds": 89,
        "outcome": "abandoned",
        "prompt_version": "v1",
        "fnol": None,
        "turns": [
            ("agent", "Hello, this is Vaani. Please share your policy number.", "POLICY_VERIFICATION"),
            ("user",  "Um... let me find it", "POLICY_VERIFICATION"),
        ],
        "metrics": [],
    },
    {
        "call_id": "demo-007",
        "channel": "phone",
        "language": "hi-IN",
        "started_at": NOW - timedelta(hours=8, minutes=15),
        "ended_at": NOW - timedelta(hours=8, minutes=10),
        "duration_seconds": 278,
        "outcome": "complete",
        "prompt_version": "v1",
        "fnol": {
            "policy_number": "TATA-GJ-2024-112233",
            "incident_type": "accident",
            "incident_date": "2024-03-10",
            "incident_location": "Ahmedabad Ring Road",
            "injuries_reported": False,
            "vehicle_damage": True,
            "damage_description": "Rear-end collision, boot damage",
            "third_party_involved": True,
            "callback_number": "9000556677",
            "preferred_language": "hi-IN",
            "completeness_score": 0.91,
            "extraction_confidence": {
                "policy_number": 0.97, "incident_type": 0.94, "incident_date": 0.89,
                "incident_location": 0.90, "vehicle_damage": 0.98, "callback_number": 0.97,
            },
        },
        "turns": [
            ("agent", "नमस्ते! पॉलिसी नंबर बताइए।", "POLICY_VERIFICATION"),
            ("user",  "TATA-GJ-2024-112233", "POLICY_VERIFICATION"),
            ("agent", "क्या हुआ?", "INCIDENT_CAPTURE"),
            ("user",  "अहमदाबाद रिंग रोड पर पीछे से टक्कर हुई।", "INCIDENT_CAPTURE"),
            ("agent", "चोट तो नहीं आई?", "DETAIL_COLLECTION"),
            ("user",  "नहीं, गाड़ी का पिछला हिस्सा टूट गया।", "DETAIL_COLLECTION"),
            ("agent", "कॉलबैक नंबर?", "CALLBACK_COLLECTION"),
            ("user",  "9000556677", "CALLBACK_COLLECTION"),
            ("agent", "क्लेम दर्ज। 24 घंटे में संपर्क होगा।", "CLOSED"),
        ],
        "metrics": [
            (305, 840, 142, 672),
            (295, 815, 138, 655),
            (315, 868, 150, 698),
        ],
    },
    {
        "call_id": "demo-008",
        "channel": "web",
        "language": "en-IN",
        "started_at": NOW - timedelta(hours=10),
        "ended_at": NOW - timedelta(hours=9, minutes=56),
        "duration_seconds": 221,
        "outcome": "complete",
        "prompt_version": "v1",
        "fnol": {
            "policy_number": "NIAC-TN-2023-998877",
            "incident_type": "accident",
            "incident_date": "2024-03-09",
            "incident_location": "Chennai OMR, Sholinganallur",
            "injuries_reported": True,
            "injury_description": "Pedestrian hit, minor injuries",
            "vehicle_damage": True,
            "third_party_involved": True,
            "callback_number": "9444667788",
            "preferred_language": "en-IN",
            "completeness_score": 0.96,
            "extraction_confidence": {
                "policy_number": 0.99, "incident_type": 0.96, "incident_date": 0.92,
                "incident_location": 0.90, "injuries_reported": 0.98,
                "third_party_involved": 0.95, "callback_number": 0.99,
            },
        },
        "turns": [
            ("agent", "Hello, this is Vaani. Policy number?", "POLICY_VERIFICATION"),
            ("user",  "NIAC-TN-2023-998877", "POLICY_VERIFICATION"),
            ("agent", "What happened?", "INCIDENT_CAPTURE"),
            ("user",  "I hit a pedestrian on OMR near Sholinganallur. Minor injuries.", "INCIDENT_CAPTURE"),
            ("agent", "Is the pedestrian receiving medical attention?", "DETAIL_COLLECTION"),
            ("user",  "Yes, ambulance has been called.", "DETAIL_COLLECTION"),
            ("agent", "Third-party involvement noted. Your callback number?", "CALLBACK_COLLECTION"),
            ("user",  "9444667788", "CALLBACK_COLLECTION"),
            ("agent", "Claim registered with third-party flag. Our team will contact you within 2 hours.", "CLOSED"),
        ],
        "metrics": [
            (288, 800, 133, 630),
            (301, 840, 141, 668),
            (294, 820, 137, 652),
        ],
    },
]

PROMPT_V1 = {
    "version_id": "v1",
    "description": "Initial production prompt — Hindi/English FNOL extraction",
    "is_active": True,
    "templates": {
        "greeting_hi": "नमस्ते! मैं वाणी हूं, आपका AI बीमा सहायक। कृपया अपनी पॉलिसी नंबर बताइए।",
        "greeting_en": "Hello! I'm Vaani, your AI insurance assistant. Please share your policy number.",
        "policy_prompt_hi": "आपकी पॉलिसी नंबर क्या है?",
        "policy_prompt_en": "What is your policy number?",
        "incident_prompt_hi": "कृपया घटना का विवरण बताइए — क्या, कब, और कहाँ हुआ?",
        "incident_prompt_en": "Please describe the incident — what happened, when, and where?",
        "callback_prompt_hi": "आपसे संपर्क करने के लिए सबसे अच्छा नंबर क्या है?",
        "callback_prompt_en": "What is the best number to reach you?",
        "close_hi": "आपकी FNOL सफलतापूर्वक दर्ज हो गई है। हम 24 घंटे में संपर्क करेंगे।",
        "close_en": "Your FNOL has been successfully registered. We'll be in touch within 24 hours.",
    },
}


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Prompt version
        existing_prompt = await session.get(PromptVersion, "v1")
        if not existing_prompt:
            session.add(PromptVersion(**PROMPT_V1, created_at=NOW - timedelta(days=7)))
            print("  + prompt version v1")

        for call_data in CALLS:
            existing = await session.get(CallRecord, call_data["call_id"])
            if existing:
                print(f"  ~ call {call_data['call_id']} already exists, skipping")
                continue

            call = CallRecord(
                call_id=call_data["call_id"],
                channel=call_data["channel"],
                language=call_data["language"],
                started_at=call_data["started_at"],
                ended_at=call_data.get("ended_at"),
                duration_seconds=call_data.get("duration_seconds"),
                outcome=call_data["outcome"],
                prompt_version=call_data["prompt_version"],
            )
            session.add(call)

            for idx, (speaker, text, state) in enumerate(call_data.get("turns", [])):
                ts_ms = int((call_data["started_at"] + timedelta(seconds=idx * 15)).timestamp() * 1000)
                session.add(ConversationTurn(
                    call_id=call_data["call_id"],
                    turn_index=idx,
                    speaker=speaker,
                    text=text,
                    language=call_data["language"],
                    timestamp_ms=ts_ms,
                    fsm_state=state,
                ))

            for idx, (stt, llm, ttft, tts) in enumerate(call_data.get("metrics", [])):
                session.add(TurnMetrics(
                    call_id=call_data["call_id"],
                    turn_index=idx,
                    stt_ms=stt,
                    llm_ms=llm,
                    llm_ttft_ms=ttft,
                    tts_ms=tts,
                    total_ms=stt + llm + tts,
                    fallback_triggered=False,
                ))

            if call_data.get("fnol"):
                f = call_data["fnol"]
                session.add(FNOLRecord(
                    call_id=call_data["call_id"],
                    policy_number=f.get("policy_number"),
                    incident_type=f.get("incident_type"),
                    incident_date=f.get("incident_date"),
                    incident_location=f.get("incident_location"),
                    injuries_reported=f.get("injuries_reported"),
                    injury_description=f.get("injury_description"),
                    vehicle_damage=f.get("vehicle_damage"),
                    damage_description=f.get("damage_description"),
                    third_party_involved=f.get("third_party_involved"),
                    callback_number=f.get("callback_number"),
                    preferred_language=f.get("preferred_language", "hi-IN"),
                    extraction_confidence=f.get("extraction_confidence", {}),
                    completeness_score=f.get("completeness_score", 0.0),
                    extracted_at=call_data.get("ended_at", NOW),
                ))

            print(f"  + call {call_data['call_id']} ({call_data['channel']}, {call_data['outcome']})")

        await session.commit()

    await engine.dispose()
    print("\nDone. Run: uvicorn app.main:app --reload --port 8000")


if __name__ == "__main__":
    asyncio.run(seed())
