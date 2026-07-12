from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from .interfaces import SpecialistRequest, SpecialistResponse

logger = logging.getLogger("aria.cto.delegation")


class SubprocessAgent:
    """Spawns specialist agents as separate Python processes.

    Communication is via stdin/stdout JSON lines.
    """

    def __init__(self, timeout: int = 120) -> None:
        self._timeout = timeout

    def spawn(self, request: SpecialistRequest) -> SpecialistResponse:
        input_payload = {
            "task": request.task_description,
            "context": {
                "files": request.context_files,
                "file_contents": request.file_contents,
                "error_output": request.error_output,
                "constraints": request.constraints,
            },
        }

        logger.info(
            "Spawning specialist %s (timeout=%ds)",
            request.specialist_name,
            self._timeout,
        )

        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "delegation.specialist_worker",
                    "--specialist",
                    request.specialist_name,
                ],
                input=json.dumps(input_payload, default=str),
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )

            if process.returncode != 0:
                return SpecialistResponse(
                    specialist_name=request.specialist_name,
                    status="failed",
                    output=process.stderr or process.stdout or "process exited with error",
                    reasoning=f"exit code {process.returncode}",
                )

            return self._parse_response(request.specialist_name, process.stdout)

        except subprocess.TimeoutExpired:
            logger.warning("Specialist %s timed out after %ds", request.specialist_name, self._timeout)
            return SpecialistResponse(
                specialist_name=request.specialist_name,
                status="failed",
                output=f"timeout after {self._timeout}s",
                reasoning="subprocess timeout",
            )
        except FileNotFoundError as exc:
            return SpecialistResponse(
                specialist_name=request.specialist_name,
                status="failed",
                output=f"python not found: {exc}",
                reasoning="interpreter not found",
            )
        except Exception as exc:
            logger.exception("Specialist spawn error")
            return SpecialistResponse(
                specialist_name=request.specialist_name,
                status="failed",
                output=str(exc),
                reasoning="unexpected error",
            )

    def _parse_response(self, name: str, raw: str) -> SpecialistResponse:
        try:
            data = json.loads(raw.strip())
            return SpecialistResponse(
                specialist_name=name,
                status=data.get("status", "failed"),
                output=data.get("output", raw),
                summary=data.get("summary", ""),
                files_modified=data.get("files_modified", []),
                diff=data.get("diff", ""),
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Failed to parse specialist output: %s", exc)
            return SpecialistResponse(
                specialist_name=name,
                status="failed",
                output=raw,
                reasoning=f"failed to parse JSON response: {exc}",
            )
