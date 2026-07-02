"""
🧬 DNA: v16.6 (Sovereign Purity)
🏢 UNIT: CHANGELOG_STUB
🛠️ ROLE: COMPATIBILITY_SHIM
📖 DESC: Stub replacing archived nlm_changelog. Keeps minimal interface for agents.
"""
import logging
log = logging.getLogger("NLM_STUB")

def log_heartbeat(agent_id: str, data: dict = None):
    """Heartbeat — the only function still called by agents."""
    return log

def log_aeo_detection(agent_id: str = "", data: dict = None, **kwargs):
    """AEO detection log — called by A12."""
    return log
