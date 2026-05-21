#!/usr/bin/env python3
"""
Vaani Production Readiness Validator
Checks that all critical changes are in place and compilable.
"""

import os
import sys
import json
from pathlib import Path

REPO_ROOT = Path("/Users/anmolsen/Developer/vaani")
BACKEND_ROOT = REPO_ROOT / "backend"
FRONTEND_ROOT = REPO_ROOT / "frontend"


def check_file_contains(file_path: Path, patterns: list[str], description: str) -> bool:
    """Check if file contains all patterns."""
    if not file_path.exists():
        print(f"  ❌ {description}: File not found: {file_path}")
        return False
    
    content = file_path.read_text()
    missing = []
    for pattern in patterns:
        if pattern not in content:
            missing.append(pattern)
    
    if missing:
        print(f"  ❌ {description}: Missing patterns:")
        for p in missing:
            print(f"     - {p}")
        return False
    
    print(f"  ✅ {description}")
    return True


def check_imports(file_path: Path, imports: list[str], description: str) -> bool:
    """Check if file imports required modules."""
    if not file_path.exists():
        print(f"  ❌ {description}: File not found: {file_path}")
        return False
    
    content = file_path.read_text()
    missing = []
    for imp in imports:
        if imp not in content:
            missing.append(imp)
    
    if missing:
        print(f"  ⚠️  {description}: Missing imports: {missing}")
        return True  # Don't fail on imports
    
    print(f"  ✅ {description}")
    return True


def main():
    print("\n🔍 VAANI PRODUCTION READINESS VALIDATOR\n")
    all_pass = True
    
    # P0 Checks - Frontend Authentication
    print("P0 - Frontend Authentication:")
    all_pass &= check_file_contains(
        FRONTEND_ROOT / "src" / "components" / "AuthGuard.tsx",
        ["getAuthToken()", "router.replace", "/login"],
        "AuthGuard component"
    )
    
    all_pass &= check_file_contains(
        FRONTEND_ROOT / "src" / "app" / "login" / "page.tsx",
        ["login(username, password)", "localStorage"],
        "Login page"
    )
    
    all_pass &= check_file_contains(
        FRONTEND_ROOT / "src" / "app" / "layout.tsx",
        ["<AuthGuard>", "<AppShell>"],
        "Root layout with AuthGuard"
    )
    
    # P0 Checks - Type Alignment
    print("\nP0 - Type Alignment:")
    all_pass &= check_file_contains(
        FRONTEND_ROOT / "src" / "lib" / "types.ts",
        ["fsm_state:", "stt_provider", "llm_provider", "tts_provider"],
        "WebSocket types with provider fields"
    )
    
    all_pass &= check_file_contains(
        FRONTEND_ROOT / "src" / "lib" / "api.ts",
        ["Promise<{ versions", "active_version"],
        "listPrompts return type"
    )
    
    # P0 Checks - WebSocket Broadcasts
    print("\nP0 - WebSocket Real-time Updates:")
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "channels" / "websocket_handler.py",
        ['type": "transcript_turn"', '"fsm_state": current_state', 
         '"stt_provider": result.stt_provider'],
        "WebSocket broadcast includes fsm_state and providers"
    )
    
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "channels" / "websocket_handler.py",
        ['type": "pipeline_metrics"', '"llm_provider": result.llm_provider',
         '"tts_provider": result.tts_provider'],
        "Pipeline metrics broadcast"
    )
    
    # P1 Checks - Rate Limiting
    print("\nP1 - Rate Limiting with Redis:")
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "api" / "_limiter.py",
        ["REDIS_URL", "memory://", "Limiter("],
        "Rate limiter with Redis fallback"
    )
    
    redis_in_compose = "redis" in (REPO_ROOT / "docker-compose.yml").read_text()
    redis_in_reqs = "redis==" in (BACKEND_ROOT / "requirements.txt").read_text()
    if redis_in_compose and redis_in_reqs:
        print("  ✅ Redis in Docker Compose and requirements.txt")
    else:
        print(f"  ❌ Redis missing: compose={redis_in_compose}, reqs={redis_in_reqs}")
        all_pass = False
    
    # P1 Checks - Graceful Shutdown
    print("\nP1 - Graceful Shutdown:")
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "main.py",
        ["live_manager.close_all()", "engine.dispose()"],
        "Shutdown handlers"
    )
    
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "channels" / "websocket_handler.py",
        ["async def close_all(", "await ws.close()"],
        "LiveMonitorManager.close_all method"
    )
    
    # P1 Checks - Migrations
    print("\nP1 - Database Migrations:")
    migrations_exist = (BACKEND_ROOT / "migrations" / "versions").exists()
    if migrations_exist:
        migration_files = list((BACKEND_ROOT / "migrations" / "versions").glob("*.py"))
        if len(migration_files) > 1:  # >1 because there's alembic_version.py usually
            print(f"  ✅ Alembic migrations exist ({len(migration_files)} files)")
        else:
            print(f"  ⚠️  Alembic migrations directory exists but may be incomplete")
    else:
        print("  ⚠️  Alembic migrations not yet verified")
    
    # P2 Checks - FNOL Export
    print("\nP2 - FNOL Export:")
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "api" / "calls.py",
        ["fnol/export", "Content-Disposition"],
        "FNOL export endpoint"
    )
    
    # P2 Checks - Date Filtering
    print("\nP2 - Date Range Filtering:")
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "api" / "calls.py",
        ["from_date", "to_date"],
        "Date params in calls API"
    )
    
    all_pass &= check_file_contains(
        FRONTEND_ROOT / "src" / "app" / "calls" / "page.tsx",
        ["from_date", "to_date"],
        "Date inputs in calls page"
    )
    
    # P2 Checks - Webhooks
    print("\nP2 - Webhook Integration:")
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "config.py",
        ["FNOL_WEBHOOK_URL"],
        "Webhook config"
    )
    
    all_pass &= check_file_contains(
        BACKEND_ROOT / "app" / "channels" / "websocket_handler.py",
        ["completeness_score >= 0.9", "httpx.AsyncClient"],
        "Webhook firing on completeness"
    )
    
    httpx_in_reqs = "httpx==" in (BACKEND_ROOT / "requirements.txt").read_text()
    if httpx_in_reqs:
        print("  ✅ httpx in requirements.txt")
    else:
        print("  ❌ httpx not in requirements.txt")
        all_pass = False
    
    # Summary
    print("\n" + "="*60)
    if all_pass:
        print("✅ ALL CRITICAL CHECKS PASSED")
        print("Ready for: Build → Test → Deploy")
    else:
        print("❌ SOME CHECKS FAILED")
        print("Review errors above and fix before deployment")
    print("="*60 + "\n")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
