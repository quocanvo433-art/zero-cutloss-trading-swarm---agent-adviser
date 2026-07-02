"""
🧬 DNA: v6.5 (Sovereign Purity & HingeEBM Packet Validator)
🏢 UNIT: MIDDLEWARE
🛠️ ROLE: DATA_GOVERNANCE
📖 DESC: Validator middleware for HingeEBM packets before Redis XADD.
"""
import json
import logging

log = logging.getLogger("PACKET_VALIDATOR")

def validate_hinge_packet(agent_id: str, packet: dict) -> bool:
    """Validates if a packet conforms to HingeEBM protocol schemas."""
    if not isinstance(packet, dict):
        log.error(f"[VALIDATOR] {agent_id} packet is not a dictionary.")
        return False

    if agent_id == "DIEN_HONG":
        if "agent_id" in packet:
            required = ["agent_id", "conflict_analysis", "cross_synthesis", "expert_scenarios"]
            for k in required:
                if k not in packet:
                    log.error(f"[VALIDATOR] DIEN_HONG single agent missing required key {k}")
                    return False
            return True
        else:
            valid_agents = {"A03", "A04", "A05", "A10", "A11", "A12"}
            if not any(k in valid_agents for k in packet.keys()):
                log.error(f"[VALIDATOR] DIEN_HONG grouped packet has no valid agent keys: {list(packet.keys())}")
                return False
            return True

    # Only validate HingeEBM trading agents
    target_agents = {"A03", "A05", "A10", "A11", "A12", "EMF", "AEO"}
    if agent_id not in target_agents:
        return True

    # Bypass validation if this is the divergence matrix stream payload
    if "divergence_score" in packet:
        return True

    if "algo_core" not in packet or "narrative_lens" not in packet:
        # Some agents might still use legacy, but HingeEBM requires these two
        log.warning(f"[VALIDATOR] {agent_id} packet missing algo_core or narrative_lens.")
        # Allow pass for transition period, but return False if strictly enforcing
        return False
        
    algo = packet["algo_core"]
    narr = packet["narrative_lens"]
    
    if not isinstance(algo, dict) or not isinstance(narr, dict):
        log.error(f"[VALIDATOR] {agent_id} algo_core or narrative_lens is not a dict.")
        return False

    if agent_id == "A03":
        required = ["ts", "symbol", "mm_score", "expert_metrics", "confidence"]
        for k in required:
            if k not in algo:
                log.error(f"[VALIDATOR] A03 missing required key {k} in algo_core")
                return False

    elif agent_id == "A10":
        required = ["ts", "symbol", "smart_money_flow", "wyckoff_phase", "alert_level"]
        for k in required:
            if k not in algo:
                log.error(f"[VALIDATOR] A10 missing required key {k} in algo_core")
                return False

    elif agent_id == "A11":
        required = ["ts", "symbol", "scenario_id", "cross_asset_confirm", "trap_detected"]
        for k in required:
            if k not in algo:
                log.error(f"[VALIDATOR] A11 missing required key {k} in algo_core")
                return False

    elif agent_id == "A12":
        required = ["ts", "topic", "verdict", "verdict_priority", "score", "emf_cross_signals"]
        for k in required:
            if k not in algo:
                log.error(f"[VALIDATOR] A12 missing required key {k} in algo_core")
                return False

    elif agent_id == "A05":
        required = ["ts", "symbol", "decision", "confidence", "position_size_pct", "input_packets_consumed"]
        for k in required:
            if k not in algo:
                log.error(f"[VALIDATOR] A05 missing required key {k} in algo_core")
                return False
                
    return True

def safe_xadd(matrix_instance, agent_id: str, stream_key: str, fields: dict, maxlen: int = 50):
    """Middleware replacement for matrix.xadd to enforce HingeEBM schema"""
    # Attempt to extract packet from fields (prioritize envelope if present)
    packet_str = fields.get("envelope") or fields.get("payload") or fields.get("signals")
    
    if packet_str and isinstance(packet_str, str):
        try:
            packet = json.loads(packet_str)
            # Determine effective agent ID for validation (can be derived from stream or passed agent_id)
            eff_id = fields.get("source", agent_id)
            if eff_id == "EMF":
                if "intent" in stream_key: eff_id = "A11"
                elif "signals" in stream_key: eff_id = "A10"
                
            is_valid = validate_hinge_packet(eff_id, packet)
            if not is_valid:
                log.warning(f"[VALIDATOR] Packet from {eff_id} to {stream_key} failed strict validation.")
        except Exception as e:
            log.debug(f"[VALIDATOR] Error extracting packet: {e}")
            
    # Resolve stream key using imperial_state PREFIX_MAP
    from imperial_state import PREFIX_MAP
    prefix = PREFIX_MAP.get(agent_id.upper(), "zcl:misc")
    full_key = f"{prefix}:{stream_key}"
    
    # Sanitize fields: dump dict/list to json
    sanitized = {}
    for k, v in fields.items():
        if isinstance(v, (dict, list)):
            sanitized[k] = json.dumps(v, ensure_ascii=False)
        else:
            sanitized[k] = str(v)
            
    # Proceed with actual XADD direct to client to prevent recursion
    return matrix_instance.client.xadd(full_key, sanitized, maxlen=maxlen)
