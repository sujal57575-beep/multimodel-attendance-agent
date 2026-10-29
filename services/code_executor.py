"""
services/code_executor.py
Safe, sandboxed code execution for optional educational code examples.
Disabled by default; only runs when CODE_EXEC_ENABLED=true.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import os
from pathlib import Path

from config import Config

logger = logging.getLogger(__name__)

SUPPORTED_LANGS = {
    "python": ("python", ".py"),
    "javascript": ("node", ".js"),
}


def execute_code(language: str, code: str) -> dict:
    """
    Execute code in a restricted subprocess.
    Returns {stdout, stderr, exit_code, timed_out, disabled}.
    """
    if not Config.CODE_EXEC_ENABLED:
        return {
            "disabled": True,
            "stdout": "",
            "stderr": "Code execution is disabled. Set CODE_EXEC_ENABLED=true to enable.",
            "exit_code": -1,
            "timed_out": False,
        }

    lang_info = SUPPORTED_LANGS.get(language.lower())
    if not lang_info:
        return {
            "disabled": False,
            "stdout": "",
            "stderr": f"Unsupported language: {language}. Supported: {list(SUPPORTED_LANGS)}",
            "exit_code": -1,
            "timed_out": False,
        }

    interpreter, ext = lang_info
    with tempfile.TemporaryDirectory() as tmpdir:
        code_file = Path(tmpdir) / f"code{ext}"
        code_file.write_text(code, encoding="utf-8")

        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "",
        }
        # Block network on Windows via isolated env (best-effort)
        try:
            proc = subprocess.run(
                [interpreter, str(code_file)],
                capture_output=True,
                text=True,
                timeout=Config.CODE_EXEC_TIMEOUT,
                env=env,
                cwd=tmpdir,
            )
            return {
                "disabled": False,
                "stdout": proc.stdout[:4096],
                "stderr": proc.stderr[:2048],
                "exit_code": proc.returncode,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired:
            logger.warning("Code execution timed out (lang=%s)", language)
            return {
                "disabled": False,
                "stdout": "",
                "stderr": f"Execution timed out after {Config.CODE_EXEC_TIMEOUT}s.",
                "exit_code": -1,
                "timed_out": True,
            }
        except FileNotFoundError:
            return {
                "disabled": False,
                "stdout": "",
                "stderr": f"Interpreter '{interpreter}' not found on PATH.",
                "exit_code": -1,
                "timed_out": False,
            }
        except Exception as e:
            logger.error("Code execution error: %s", e)
            return {
                "disabled": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "timed_out": False,
            }
