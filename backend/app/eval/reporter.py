"""Eval reporter — generates markdown report from eval run results."""
from __future__ import annotations

from datetime import datetime


def generate_report(
    run_id: str,
    prompt_version_id: str,
    summary: dict,
    scenario_results: dict,
) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = summary.get("total_scenarios", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    accuracy = summary.get("overall_accuracy", 0.0)
    per_field = summary.get("per_field_accuracy", {})
    baseline_delta = summary.get("baseline_delta")

    lines: list[str] = [
        f"# Vaani Eval Report — {prompt_version_id}",
        f"",
        f"**Run ID**: `{run_id}`  ",
        f"**Version**: `{prompt_version_id}`  ",
        f"**Generated**: {now}  ",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Scenarios | {total} |",
        f"| Passed | {passed} ✅ |",
        f"| Failed | {failed} ❌ |",
        f"| **Overall Accuracy** | **{accuracy:.1%}** |",
    ]

    if baseline_delta:
        for field, delta in baseline_delta.items():
            arrow = "↑" if delta > 0 else "↓" if delta < 0 else "→"
            lines.append(f"| Δ {field} vs baseline | {arrow} {delta:+.1%} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## Per-Field Accuracy",
        f"",
        f"| Field | Accuracy |",
        f"|-------|----------|",
    ]

    for field, acc in sorted(per_field.items(), key=lambda x: x[1], reverse=True):
        bar = "█" * int(acc * 10) + "░" * (10 - int(acc * 10))
        lines.append(f"| {field} | `{bar}` {acc:.1%} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## Scenario Results",
        f"",
        f"| ID | Name | Accuracy | Status |",
        f"|----|------|----------|--------|",
    ]

    for scenario_id, result in scenario_results.items():
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        acc_pct = f"{result['overall_accuracy']:.1%}"
        lines.append(f"| {scenario_id} | {result['name']} | {acc_pct} | {status} |")

    lines += ["", "---", "", "## Detailed Field Breakdown", ""]

    for scenario_id, result in scenario_results.items():
        lines += [
            f"### {scenario_id} — {result['name']}",
            f"",
            f"**Overall**: {result['overall_accuracy']:.1%} | {'PASS ✅' if result['passed'] else 'FAIL ❌'}",
            f"",
            f"| Field | Expected | Extracted | Score |",
            f"|-------|----------|-----------|-------|",
        ]
        for detail in result.get("field_details", []):
            score_display = f"{'✅' if detail['score'] >= 0.8 else '❌'} {detail['score']:.0%}"
            expected_str = str(detail["expected"])[:40]
            extracted_str = str(detail["extracted"])[:40] if detail["extracted"] is not None else "—"
            lines.append(
                f"| {detail['field']} | {expected_str} | {extracted_str} | {score_display} |"
            )
        lines.append("")

    return "\n".join(lines)
