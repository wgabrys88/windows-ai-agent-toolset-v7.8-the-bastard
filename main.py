from __future__ import annotations
import os
import sys
from winapi import winapi_init_dpi
from scenarios import TOOLS_SCHEMA, SYSTEM_PROMPT
from agent import run_agent
from utils import utils_get_env_str, utils_get_env_int, utils_get_env_float


def main() -> None:
    winapi_init_dpi()
    task_prompt = input().strip()
    if not task_prompt:
        sys.exit("Error: No task provided.")
    
    cfg = {
        "endpoint": utils_get_env_str("LMSTUDIO_ENDPOINT", "http://localhost:1234/v1/chat/completions"),
        "model_id": utils_get_env_str("LMSTUDIO_MODEL", "qwen3-vl-8b-instruct"),
        "timeout": utils_get_env_int("LMSTUDIO_TIMEOUT", 240),
        "temperature": utils_get_env_float("LMSTUDIO_TEMPERATURE", 0.5),
        "max_tokens": utils_get_env_int("LMSTUDIO_MAX_TOKENS", 2048),
        "target_w": utils_get_env_int("AGENT_IMAGE_W", 1536),
        "target_h": utils_get_env_int("AGENT_IMAGE_H", 864),
        "dump_dir": utils_get_env_str("AGENT_DUMP_DIR", "dumps"),
        "dump_prefix": utils_get_env_str("AGENT_DUMP_PREFIX", "screen_"),
        "dump_start": utils_get_env_int("AGENT_DUMP_START", 1),
        "max_steps": utils_get_env_int("AGENT_MAX_STEPS", 50),
        "step_delay": utils_get_env_float("AGENT_STEP_DELAY", 0.4),
    }
    
    os.makedirs(cfg["dump_dir"], exist_ok=True)
    
    try:
        out = run_agent(SYSTEM_PROMPT, task_prompt, TOOLS_SCHEMA, cfg)
        if out:
            print(out)
    except Exception as e:
        print(f"\nException occurred: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
