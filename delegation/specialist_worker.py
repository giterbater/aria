from __future__ import annotations

import argparse
import json
import sys

from prompts.specialist_mimo import MIMO_SPECIALIST_PROMPT
from prompts.specialist_nemotron import NEMOTRON_SPECIALIST_PROMPT


SPECIALIST_PROMPTS = {
    "mimo": MIMO_SPECIALIST_PROMPT,
    "nemotron": NEMOTRON_SPECIALIST_PROMPT,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Specialist worker process")
    parser.add_argument("--specialist", required=True, choices=["mimo", "nemotron"])
    args = parser.parse_args()

    raw_input = sys.stdin.read()
    try:
        data = json.loads(raw_input)
    except json.JSONDecodeError:
        print(json.dumps({"status": "failed", "output": "invalid JSON input"}))
        sys.exit(1)

    task = data.get("task", "")
    context = data.get("context", {})
    files = context.get("files", [])
    file_contents = context.get("file_contents", {})
    error_output = context.get("error_output", "")

    context_parts = []
    for f in files:
        if f in file_contents:
            context_parts.append(f"--- {f} ---\n{file_contents[f]}")
        else:
            context_parts.append(f"--- {f} --- (not provided)")

    if error_output:
        context_parts.append(f"--- Error Output ---\n{error_output}")

    template = SPECIALIST_PROMPTS[args.specialist]
    prompt = template.format(
        task_description=task,
        context_files="\n".join(context_parts),
        additional_context="",
    )

    print(json.dumps({
        "status": "success",
        "summary": f"Specialist {args.specialist} processed task",
        "files_modified": [],
        "reasoning": f"Task received: {task[:200]}",
        "output": f"Specialist {args.specialist} is a placeholder. Implement LLM-based processing for real delegation.",
    }))


if __name__ == "__main__":
    main()
