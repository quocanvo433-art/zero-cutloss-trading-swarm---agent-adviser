"""
🧬 DNA: v16.6 (Sovereign Purity & Diagnostics)
🏢 UNIT: DPO_REPORT
🛠️ ROLE: DIAGNOSTICIAN
📖 DESC: 24h DPO performance reporting system, summarizing Winrate, Drawdown, and Dataset health metrics from the Matrix (Redis).
🔗 CALLS: tools/imperial_state.py
📟 I/O: Redis: zcl:A04:*, zcl:A05:*, logs/agent_execution.log
🛡️ INTEGRITY: Calibration-Brier, Winrate-Windows, Drawdown-Quality.
"""

import os
import json
import time
import glob
import logging
from datetime import datetime, timezone
from typing import Optional

from imperial_state import matrix
from dotenv import load_dotenv

# ── Load env ──────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../config/.env'))

BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DPO_DIR         = os.path.join(BASE_DIR, "dpo_lab")
CHECKPOINTS_DIR = os.path.join(DPO_DIR, "checkpoints")

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger("05_DIVINE_EYE_REPORT")
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "logs", "agent_execution.log")),
        logging.StreamHandler(),
    ]
)

# ══════════════════════════════════════════════════════════════════════════════
# PART 1 — MATRIX QUERY
# ══════════════════════════════════════════════════════════════════════════════

def _lay_chi_so_tu_matrix(agent_id: str, key: str) -> dict:
    """Get calculated indicators from the Matrix"""
    try:
        data = matrix.get(agent_id, key)
        if data:
            if isinstance(data, dict):
                return data
            return json.loads(str(data))
    except Exception as e:
        log.warning(f"Error reading Matrix {agent_id}:{key} -> {e}")
    return {}


# ══════════════════════════════════════════════════════════════════════════════
# PART 2 — HELPERS
# ══════════════════════════════════════════════════════════════════════════════

# Checkpoint helpers removed as Matrix handles all state now.


def _tao_alerts(cs1, cs2, cs3, cs4, cs5, cs6) -> list[dict]:
    """Analyze 6 metric groups → create high-priority alert list"""
    alerts = []
    # Drop in win rate
    wr_7d  = cs2.get("7_days", {}).get("win_rate_pct")
    wr_30d = cs2.get("30_days", {}).get("win_rate_pct")
    if wr_7d is not None and wr_30d is not None and wr_7d < wr_30d - 10:
        alerts.append({
            "severity": "HIGH",
            "label": "WIN_RATE_SHARP_DROP",
            "description": f"7-day win rate ({wr_7d}%) is lower than 30-day win rate ({wr_30d}%)",
            "guideline": "Check DPO diagnosis immediately.",
        })
    # Low Drawdown health
    dd_health = cs3.get("health_index")
    if dd_health is not None and dd_health < 60:
        alerts.append({
            "severity": "MEDIUM",
            "label": "DRAWDOWN_HEALTH_LOW",
            "description": f"DD health low: {dd_health}%",
        })
    return alerts


def _build_telegram_message(report: dict) -> str:
    """Shortened version for Telegram"""
    cs1 = report.get("metric_1_dataset", {})
    cs2 = report.get("metric_2_win_rate", {})
    cs3 = report.get("metric_3_drawdown", {})
    cs6 = report.get("metric_6_training", {})
    alerts = report.get("alerts", [])

    lines = [
        f"🧠 *DPO DAILY REPORT*",
        f"_{report.get('timestamp_readable', '')}_",
        f"━━━━━━━━━━━━━━━",
        f"📦 DPO real pairs: *{cs1.get('total_dpo_real_pairs', '?')}*",
        f"📈 Win rate 7d: *{cs2.get('7_days', {}).get('win_rate_pct', '?')}%*",
        f"💧 DD health: *{cs3.get('health_index', '?')}%*",
    ]
    
    high_alerts = [a for a in alerts if a["severity"] == "HIGH"]
    if high_alerts:
        lines.append("🚨 *ALERTS:* " + ", ".join(a["label"] for a in high_alerts))
        
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# PART 3 — MAIN FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def tao_bao_cao_dpo_24h(on_demand: bool = False) -> str:
    """Generate stateless 24h DPO report"""
    timestamp_unix = int(time.time())
    log.info("=== A05 REPORT: Creating Stateless DPO Report ===")

    # Fetch from Matrix
    cs1 = _lay_chi_so_tu_matrix("A04", "dataset_size:latest")
    cs2 = _lay_chi_so_tu_matrix("A04", "winrate:latest")
    cs3 = _lay_chi_so_tu_matrix("A04", "drawdown:latest")
    cs4 = _lay_chi_so_tu_matrix("A05", "wyckoff_accuracy:latest")
    cs5 = _lay_chi_so_tu_matrix("A05", "calibration:latest")
    cs6 = {}
    cs7 = _lay_chi_so_tu_matrix("A04", "blind_health:latest")

    if not cs1 and not cs2:
        log.warning("Matrix is empty. Waiting for sensors...")
        result = {
            "agent_id":          "05_DIVINE_EYE",
            "report_type":       "DPO_24H_REPORT",
            "timestamp_unix":    timestamp_unix,
            "warning":           "WAITING_FOR_MATRIX",
        }
        return json.dumps(result, ensure_ascii=False)

    alerts = _tao_alerts(cs1, cs2, cs3, cs4, cs5, cs6)

    # Adaptive loop feedback
    if cs7.get("health_status") == "ADJUSTMENT_REQUIRED":
        alerts.append({
            "severity": "MEDIUM",
            "label": "BLIND_ACC_LOW",
            "description": f"A04 accuracy {cs7.get('accuracy_blind_pct')}%",
            "guideline": "Auditor is adjusting bias.",
        })

    report = {
        "agent_id":           "05_DIVINE_EYE",
        "report_type":        "DPO_24H_REPORT",
        "timestamp_unix":     timestamp_unix,
        "timestamp_readable": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        "on_demand":          on_demand,

        "metric_1_dataset":       cs1,
        "metric_2_win_rate":      cs2,
        "metric_3_drawdown":      cs3,
        "metric_4_wyckoff":       cs4,
        "metric_5_calibration":   cs5,
        "metric_6_training":      cs6,
        "metric_7_blind_health":  cs7,
        "alerts":                 alerts,
        "high_alert_count":       sum(1 for a in alerts if a["severity"] == "HIGH"),
        "medium_alert_count":     sum(1 for a in alerts if a["severity"] == "MEDIUM"),

        "telegram_summary": _build_telegram_message({
            "metric_1_dataset": cs1, "metric_2_win_rate": cs2,
            "metric_3_drawdown": cs3, "metric_6_training": cs6,
            "alerts": alerts, "timestamp_readable": datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        }),
    }

    matrix.set("A05", "report", report, expire=90000)
    return json.dumps(report, ensure_ascii=False)


# ── Tool Definition for OpenClaw ──────────────────────────────────────────────
TOOL_DEFINITION = {
    "name": "tao_bao_cao_dpo_24h",
    "description": "Divine Eye — Claw 2: 24h DPO quality report from Matrix.",
    "parameters": {
        "type": "object",
        "properties": {
            "on_demand": {"type": "boolean", "default": False},
        },
    },
}


if __name__ == "__main__":
    print("=== TEST Stateless DPO Report ===")
    print(tao_bao_cao_dpo_24h(on_demand=True))


# ════════════════════════════════════════════════════════════════════════════════
# PART 4 — POSTMORTEM FORMATTER
# ════════════════════════════════════════════════════════════════════════════════

def format_postmortem_for_telegram(record: dict) -> str:
    """Format post-mortem report for Telegram command /judge"""
    if not record: return "⚠️ No post-mortem available."
    report = record.get("report", {})
    mode = record.get("mode", "HUNTING")
    snap = record.get("snapshot_id", "?")
    
    # Use standard keys from Trinity Auditor v16.9
    err_dissect = report.get("step1_dissect_student_error") or report.get("step_1_signal_misunderstood", "N/A")
    lesson = report.get("step3_core_lesson") or report.get("lesson_for_9b", "N/A")

    lines = [
        f"🎯 *POST-MORTEM 235B — {mode}*",
        f"_{snap}_",
        f"━━━━━━━━━━━━━━",
        f"🧠 *Error:* {str(err_dissect)[:250]}",
        f"📚 *Lesson:* {str(lesson)[:250]}",
        f"📊 Quality: *{report.get('quality_score', '?')}/100*",
    ]
    return "\n".join(lines)


def get_recent_postmortems(n: int = 5) -> list:
    """Get N most recent post-mortems from Matrix"""
    try:
        raw_list = matrix.lrange("A05", "postmortem:history", -n, -1)
        if not raw_list: return []
        return [json.loads(item) if isinstance(item, str) else item for item in reversed(raw_list)]
    except Exception: return []


def get_riding_errors_active() -> list:
    """Get active riding alerts"""
    try:
        snaps = matrix.smembers("A05", "active_riding_snaps")
        result = []
        for snap_id in snaps:
            data = matrix.get("A05", f"riding_alert:{snap_id}")
            if data: result.append(json.loads(data) if isinstance(data, str) else data)
        return sorted(result, key=lambda x: x.get("ts", 0), reverse=True)
    except Exception: return []
