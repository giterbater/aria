from __future__ import annotations

REVIEW_PROMPT = """You are a senior code reviewer. Review the following changes for quality.

## Diff

{diff}

## Context

{context}

## Review Criteria

1. **Architecture**: Does the change follow the project's patterns (Protocol-based DI, frozen dataclasses, never-raise)?
2. **Correctness**: Is the logic correct? Are edge cases handled?
3. **Style**: Does it match the existing code style? No unnecessary comments or abstractions?
4. **Tests**: Are there adequate tests? Do existing tests still pass?
5. **Regressions**: Could this change break existing functionality?

## Response Format

Respond with a JSON object:
```json
{{
  "approved": true | false,
  "issues": ["issue 1", "issue 2"],
  "suggestions": ["suggestion 1", "suggestion 2"],
  "summary": "Brief overall assessment"
}}
```
"""

FAILURE_ANALYSIS_PROMPT = """A test run failed. Analyze the failures and suggest fixes.

## Test Output

{test_output}

## Changed Files

{changed_files}

## Response Format

Respond with a JSON object:
```json
{{
  "root_cause": "Description of why tests are failing",
  "fix_suggestion": {{
    "action": "<tool_name>",
    "args": {{ ... }},
    "reasoning": "Why this fix addresses the root cause"
  }},
  "files_likely_affected": ["path/to/file.py"]
}}
```
"""
