"""NCore Genesis — Validation Layer
Self-correcting validation with retry logic for agent outputs.
"""
from __future__ import annotations
import asyncio
import json
from typing import Dict, List, Any, Optional
import httpx
import structlog

log = structlog.get_logger()

# Local validator model (cheap, fast)
VALIDATOR_MODEL = "openai/gpt-4.1-nano"  # or local model if available
LOCAL_VALIDATOR_URL = "http://localhost:9090"  # llama-server


async def validate_output(task_id: str, role: str, output: str, criteria: List[str],
                          client: httpx.AsyncClient, is_local: bool = False) -> Dict[str, Any]:
    """Validate agent output using a critic model.
    
    Args:
        task_id: Task identifier for logging
        role: Agent role (e.g., "Researcher", "Writer")
        output: Agent's output to validate
        criteria: List of validation criteria (e.g., "correctness", "completeness")
        client: HTTP client for model calls
        is_local: Whether to use local validator (uncensored, $0)
        
    Returns:
        Dict with validation results:
        {
            "valid": bool,
            "issues": ["list of issues found"],
            "suggestion": "how to fix issues",
            "confidence": 0.95
        }
    """
    log.info("validation.start", task_id=task_id, role=role, criteria=criteria)
    
    # Build validation prompt
    prompt = f"""You are a validation expert. Check this agent output against the criteria.

AGENT ROLE: {role}
OUTPUT:
{output}

VALIDATION CRITERIA:
{chr(10).join(f"- {c}" for c in criteria)}

RESPOND ONLY IN JSON:
{{
  "valid": true/false,
  "issues": ["specific issues found, if any"],
  "suggestion": "concise fix suggestion, if invalid",
  "confidence": 0.0-1.0
}}"""
    
    # Call validator model
    try:
        if is_local:
            response = await client.post(
                f"{LOCAL_VALIDATOR_URL}/v1/completions",
                json={
                    "prompt": prompt,
                    "max_tokens": 300,
                    "temperature": 0.1,
                    "stop": ["\n\n"],
                },
                timeout=30.0
            )
            result_text = response.json()["choices"][0]["text"].strip()
        else:
            # Use OpenRouter for cloud validation
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_key()}",
                    "HTTP-Referer": "http://ncore.internal",
                    "X-Title": "NCore Validator",
                },
                json={
                    "model": VALIDATOR_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 300,
                },
                timeout=30.0
            )
            result_text = response.json()["choices"][0]["message"]["content"].strip()
        
        # Parse JSON response
        try:
            result = json.loads(result_text)
            if not isinstance(result, dict):
                raise ValueError("Not a dict")
        except (json.JSONDecodeError, ValueError):
            # Fallback: extract JSON from text
            import re
            match = re.search(r"\{.*\}", result_text, re.DOTALL)
            if match:
                result = json.loads(match.group())
            else:
                raise ValueError(f"Invalid JSON in validator response: {result_text[:100]}")
        
        # Ensure required fields
        result.setdefault("valid", False)
        result.setdefault("issues", [])
        result.setdefault("suggestion", "")
        result.setdefault("confidence", 0.5)
        
        log.info("validation.complete", task_id=task_id, role=role, valid=result["valid"])
        return result
        
    except Exception as e:
        log.error("validation.error", task_id=task_id, role=role, error=str(e))
        return {
            "valid": False,
            "issues": [f"Validation error: {e}"],
            "suggestion": "Re-run agent with clearer instructions",
            "confidence": 0.0
        }


def openrouter_key() -> str:
    """Get OpenRouter API key from environment."""
    import os
    return os.environ.get("OPENROUTER_API_KEY", "")


# Default validation criteria by agent type
DEFAULT_CRITERIA = {
    "Researcher": ["accuracy", "completeness", "citations"],
    "Writer": ["clarity", "structure", "grammar"],
    "Coder": ["syntax", "logic", "efficiency", "security"],
    "Analyst": ["insight", "data_support", "objectivity"],
    "Planner": ["feasibility", "clarity", "coverage"],
    "default": ["relevance", "coherence", "conciseness"]
}


def get_criteria_for_role(role: str) -> List[str]:
    """Get validation criteria for an agent role."""
    for key, criteria in DEFAULT_CRITERIA.items():
        if key.lower() in role.lower():
            return criteria
    return DEFAULT_CRITERIA["default"]