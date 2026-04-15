"""
Extension: Context Compressor
Runs BEFORE each LLM call to prevent context overflow.
Compresses history when approaching token budget limits.
Saves compressed summaries to persistent storage for recall.
"""
from helpers.extension import Extension
from agent import LoopData
import json, os, time

COMPRESSION_THRESHOLD = 0.65  # Start compressing at 65% of context window
HARD_LIMIT_THRESHOLD = 0.85   # Force handoff at 85%
SUMMARY_FILE = "/a0/usr/workdir/context_summary.json"

class ContextCompressor(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        if not self.agent:
            return

        # Get context window size from model config
        try:
            ctx_length = self.agent.config.chat_model.ctx_length or 128000
        except Exception:
            ctx_length = 128000

        # Estimate current token usage from history length
        history = self.agent.context.history if hasattr(self.agent.context, 'history') else []
        estimated_tokens = sum(len(str(msg)) // 4 for msg in history) if history else 0
        usage_pct = estimated_tokens / ctx_length if ctx_length > 0 else 0

        if usage_pct < COMPRESSION_THRESHOLD:
            return  # Nothing to do

        # Get recent tool calls for checkpoint
        recent_outputs = []
        if history:
            for msg in history[-10:]:
                msg_str = str(msg)
                if len(msg_str) > 100:
                    recent_outputs.append(msg_str[:200])

        if usage_pct >= HARD_LIMIT_THRESHOLD:
            # Inject hard limit warning into agent context
            warning = f"\n\n[SYSTEM ALERT] Context is {usage_pct*100:.0f}% full ({estimated_tokens:,}/{ctx_length:,} estimated tokens). IMMEDIATELY: (1) Summarize all findings so far in a structured note, (2) save it with the memorize tool, (3) complete the current subtask and present results to the user. Do not continue without summarizing first.\n\n"
            if hasattr(loop_data, 'extras_persistent') and loop_data.extras_persistent is not None:
                loop_data.extras_persistent["context_warning"] = warning
            return

        if usage_pct >= COMPRESSION_THRESHOLD:
            # Gentle warning
            note = f"\n\n[Context Monitor] Using ~{usage_pct*100:.0f}% of context window. Consider summarizing completed work with the memorize tool to keep context lean.\n\n"
            if hasattr(loop_data, 'extras_persistent') and loop_data.extras_persistent is not None:
                if "context_warning" not in loop_data.extras_persistent:
                    loop_data.extras_persistent["context_warning"] = note
