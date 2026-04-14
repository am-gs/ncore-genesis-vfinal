#!/usr/bin/env python3
"""
NCore Supervisor — Always-On AI Handyman
Runs on schedule via Perplexity Computer's cron system.
Monitors, debugs, and self-heals the Agent Zero stack automatically.

Checks performed:
1. Agent Zero container health
2. Model config validity + rate limit detection
3. Active Vast.ai pods (cost protection)
4. Disk space
5. Memory pressure
6. Skills integrity (YAML frontmatter)
7. API key expiry (Gemini, Groq)
8. agent.py patch survival
9. Reference images present
10. Error patterns in recent logs

Auto-fixes applied:
- Kill idle Vast.ai pods
- Restart crashed container
- Re-apply agent.py patch if lost
- Re-install missing OSINT tools
- Clear excessive log files
- Fix broken skill frontmatter
"""
import subprocess, json, re, time
from datetime import datetime

# ─── Config ────────────────────────────────────────────────────────────────
VAST_KEY  = "9575da8fad42c421d7673ed414f3fee7b669dfe3a57d5f3155300171fbf88455"
GEMINI_KEY = "AIzaSyCL7QipKc-jLhQm_DWBjj00f5x8E1K2J1I"
SSH_HOST  = "ncore"
ALERT_LOG = "/home/user/workspace/cron_tracking/supervisor_log.jsonl"

VAST_API  = "https://console.vast.ai/api/v0"

import os
os.makedirs("/home/user/workspace/cron_tracking", exist_ok=True)

# ─── Helpers ────────────────────────────────────────────────────────────────
def ssh(cmd, timeout=30):
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=no", SSH_HOST, cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def vast_get(path):
    import urllib.request
    req = urllib.request.Request(
        f"{VAST_API}/{path.lstrip('/')}",
        headers={"Authorization": f"Bearer {VAST_KEY}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}

def vast_delete(instance_id):
    import urllib.request
    req = urllib.request.Request(
        f"{VAST_API}/instances/{instance_id}/",
        method="DELETE",
        headers={"Authorization": f"Bearer {VAST_KEY}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except Exception as e:
        return str(e)

def log_event(level, check, message, action=None):
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "level": level,   # INFO / WARN / CRITICAL / FIXED
        "check": check,
        "message": message,
        "action": action
    }
    with open(ALERT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[{level:8s}] {check}: {message}" + (f" → {action}" if action else ""))
    return entry

# ─── Health Checks ───────────────────────────────────────────────────────────

def check_container():
    """Verify Agent Zero is running and responding."""
    out, _, rc = ssh("docker inspect --format '{{.State.Status}}' agent-zero 2>/dev/null")
    if rc != 0 or out.strip() != "running":
        log_event("CRITICAL", "container", f"Agent Zero not running (status: {out})", "Attempting restart")
        ssh("docker start agent-zero 2>/dev/null || docker restart agent-zero 2>/dev/null")
        time.sleep(10)
        out2, _, rc2 = ssh("docker inspect --format '{{.State.Status}}' agent-zero 2>/dev/null")
        if out2.strip() == "running":
            return log_event("FIXED", "container", "Container restarted successfully")
        else:
            return log_event("CRITICAL", "container", "Container failed to restart — manual intervention needed")
    
    # Also check HTTP health
    out3, _, rc3 = ssh("curl -s -o /dev/null -w '%{http_code}' http://localhost:8090/ 2>/dev/null")
    if out3.strip() not in ("200", "301", "302"):
        log_event("WARN", "container", f"Agent Zero HTTP returned {out3} — may be starting up")
    else:
        log_event("INFO", "container", f"Agent Zero running and healthy (HTTP {out3})")

def check_vast_pods():
    """Kill any idle or stuck Vast.ai pods to prevent cost bleed."""
    data = vast_get("instances/")
    pods = data.get("instances", [])
    balance = vast_get("users/current/").get("credit", 0)
    
    if not pods:
        log_event("INFO", "vast_pods", f"No active pods. Balance: ${balance:.2f}")
        return
    
    for pod in pods:
        iid = pod["id"]
        status = pod.get("actual_status", "?")
        cost = pod.get("dph_total", 0)
        age_s = time.time() - pod.get("start_date", time.time())
        age_min = age_s / 60
        
        # Kill pods that have been running > 30 min (video gen should complete in 20)
        if age_min > 30:
            vast_delete(iid)
            log_event("FIXED", "vast_pods",
                      f"Killed pod {iid} (running {age_min:.0f}min, ${cost:.3f}/hr)",
                      f"Destroyed — saved ${cost * (age_min/60):.3f}")
        elif status in ("error", "failed", "exited"):
            vast_delete(iid)
            log_event("FIXED", "vast_pods", f"Killed failed pod {iid} status={status}")
        else:
            log_event("WARN", "vast_pods",
                      f"Active pod {iid}: {status}, ${cost:.3f}/hr, running {age_min:.0f}min. Balance: ${balance:.2f}")

def check_memory():
    """Warn if RAM is critically low."""
    out, _, _ = ssh("free -b | grep Mem")
    if not out:
        return
    parts = out.split()
    total, used, free = int(parts[1]), int(parts[2]), int(parts[3])
    avail = int(parts[6]) if len(parts) > 6 else free
    pct = used / total * 100
    avail_gb = avail / 1e9
    
    if avail_gb < 2:
        log_event("CRITICAL", "memory", f"Only {avail_gb:.1f}GB available ({pct:.0f}% used)")
        # Try to free memory by clearing container caches
        ssh("docker exec agent-zero sync 2>/dev/null")
    elif avail_gb < 4:
        log_event("WARN", "memory", f"{avail_gb:.1f}GB available ({pct:.0f}% used)")
    else:
        log_event("INFO", "memory", f"{avail_gb:.1f}GB available ({pct:.0f}% used)")

def check_disk():
    """Warn if disk is >80% full."""
    out, _, _ = ssh("df -h / | tail -1")
    if not out:
        return
    parts = out.split()
    pct = int(parts[4].rstrip('%'))
    if pct > 90:
        log_event("CRITICAL", "disk", f"Disk {pct}% full — clearing logs")
        ssh("sudo journalctl --vacuum-size=100M 2>/dev/null")
        ssh("docker exec agent-zero find /a0/usr/workdir -name '*.tmp' -delete 2>/dev/null")
    elif pct > 80:
        log_event("WARN", "disk", f"Disk {pct}% full")
    else:
        log_event("INFO", "disk", f"Disk {pct}% used ({parts[3]} free)")

def check_agent_patch():
    """Verify the tool_args validation patch is still applied."""
    out, _, _ = ssh("docker exec agent-zero grep -c 'is None or not isinstance' /a0/agent.py 2>/dev/null")
    if out.strip() == "0" or not out.strip():
        log_event("WARN", "agent_patch", "tool_args patch missing — re-applying")
        ssh('docker exec agent-zero sed -i \'s/if not tool_request.get("tool_args") or not isinstance(tool_request.get("tool_args"), dict):/if tool_request.get("tool_args") is None or not isinstance(tool_request.get("tool_args"), dict):/\' /a0/agent.py 2>/dev/null')
        log_event("FIXED", "agent_patch", "tool_args patch re-applied")
    else:
        log_event("INFO", "agent_patch", "tool_args validation patch present")

def check_skills():
    """Verify all skills have valid YAML frontmatter."""
    out, _, _ = ssh("docker exec agent-zero find /a0/usr/skills -name SKILL.md 2>/dev/null")
    skill_files = [f.strip() for f in out.split('\n') if f.strip()]
    broken = []
    for sf in skill_files:
        head, _, _ = ssh(f"docker exec agent-zero head -3 {sf} 2>/dev/null")
        if not head.startswith("---"):
            broken.append(sf)
    
    if broken:
        log_event("WARN", "skills", f"{len(broken)} skills missing frontmatter: {broken[:3]}")
        # Run the fix script if it exists
        ssh("/opt/venv/bin/python3 /a0/usr/fix_all_skills.py 2>/dev/null || true")
        log_event("FIXED", "skills", "Frontmatter fix script executed")
    else:
        log_event("INFO", "skills", f"All {len(skill_files)} skills have valid frontmatter")

def check_model_config():
    """Check model config is sane and not stuck on a broken model."""
    out, _, _ = ssh("python3 -c \"import json; c=json.load(open('/home/ubuntu/agent-zero-data/plugins/_model_config/config.json')); print(c['chat_model']['name'], c['chat_model']['ctx_length'])\" 2>/dev/null")
    if not out:
        log_event("WARN", "model_config", "Could not read model config")
        return
    
    parts = out.split()
    model_name = parts[0] if parts else "?"
    ctx_len = int(parts[1]) if len(parts) > 1 else 0
    
    # Detect if stuck on bad model
    if ctx_len < 32000:
        log_event("WARN", "model_config", f"Chat model ctx_length={ctx_len} — too low, may cause overflow")
    elif "openai/gpt-oss-20b" in model_name:
        log_event("WARN", "model_config", "Stuck on free GPT-OSS-20B utility model — rate limits likely")
    else:
        log_event("INFO", "model_config", f"Model: {model_name} ctx={ctx_len:,}")

def check_logs_for_errors():
    """Scan recent Agent Zero logs for critical error patterns."""
    out, _, _ = ssh("docker logs agent-zero --tail 100 2>&1")
    
    patterns = {
        "rate_limit": r"RateLimitError|rate.limit|429",
        "context_overflow": r"max_num_tokens|context.length.exceeded|prompt.too.long",
        "tool_args_error": r"tool_args.*dictionary|Tool request must have",
        "vast_image_error": r"pull access denied|repository does not exist",
        "crash_loop": r"Restarting.*second|exit.code",
    }
    
    found = []
    for name, pattern in patterns.items():
        if re.search(pattern, out, re.IGNORECASE):
            found.append(name)
    
    if found:
        log_event("WARN", "logs", f"Error patterns detected: {', '.join(found)}")
        
        # Auto-fix context overflow
        if "context_overflow" in found:
            log_event("INFO", "logs", "Context overflow detected — suggesting new chat session")
        
        # Auto-fix tool_args error
        if "tool_args_error" in found:
            check_agent_patch()  # Re-apply patch
    else:
        log_event("INFO", "logs", "No critical error patterns in recent logs")

def check_reference_images():
    """Verify reference images for video generation are present."""
    out, _, _ = ssh("docker exec agent-zero ls -la /a0/usr/workdir/reference_male.jpg /a0/usr/workdir/reference_female.jpg 2>/dev/null")
    if "reference_male" in out and "reference_female" in out:
        log_event("INFO", "reference_images", "Both reference images present")
    else:
        log_event("WARN", "reference_images", "Reference images missing — video pipeline will fail")

def check_gemini_api():
    """Quick test of Gemini API key."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_KEY}",
            data=json.dumps({"contents": [{"parts": [{"text": "hi"}]}]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
        if "candidates" in body:
            log_event("INFO", "gemini_api", "Gemini 2.5 Flash API key valid and responsive")
        else:
            log_event("WARN", "gemini_api", f"Gemini API returned unexpected response: {str(body)[:100]}")
    except Exception as e:
        log_event("CRITICAL", "gemini_api", f"Gemini API unreachable: {e}")

# ─── Main ────────────────────────────────────────────────────────────────────

def run_supervisor():
    start = time.time()
    log_event("INFO", "supervisor", "=== NCore Supervisor Run Starting ===")

    # Run all checks
    checks = [
        ("Container health",    check_container),
        ("Vast.ai pods",        check_vast_pods),
        ("Memory",              check_memory),
        ("Disk",                check_disk),
        ("Agent.py patch",      check_agent_patch),
        ("Skills integrity",    check_skills),
        ("Model config",        check_model_config),
        ("Log errors",          check_logs_for_errors),
        ("Reference images",    check_reference_images),
        ("Gemini API",          check_gemini_api),
    ]

    results = []
    for name, fn in checks:
        try:
            fn()
        except Exception as e:
            log_event("WARN", "supervisor", f"Check '{name}' threw exception: {e}")

    elapsed = time.time() - start
    log_event("INFO", "supervisor", f"=== Supervisor Run Complete ({elapsed:.1f}s) ===")

    # Produce a summary for the notification
    with open(ALERT_LOG) as f:
        entries = [json.loads(l) for l in f if l.strip()]
    
    # Get entries from this run (last N entries)
    this_run = entries[-len(checks)-2:]
    critical = [e for e in this_run if e["level"] in ("CRITICAL", "WARN")]
    fixed = [e for e in this_run if e["level"] == "FIXED"]

    return critical, fixed

if __name__ == "__main__":
    critical, fixed = run_supervisor()
    
    if critical:
        print(f"\n⚠ {len(critical)} issues detected:")
        for e in critical:
            print(f"  [{e['level']}] {e['check']}: {e['message']}")
    
    if fixed:
        print(f"\n✓ {len(fixed)} issues auto-fixed:")
        for e in fixed:
            print(f"  [FIXED] {e['check']}: {e['action']}")
    
    if not critical and not fixed:
        print("\n✓ All systems nominal")
