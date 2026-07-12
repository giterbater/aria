# Execution Architecture

Execution is routed through `SkillManager`.

## Components

- `SkillRegistry`: registers, enables, disables, and discovers skills.
- `SkillRouter`: resolves task descriptions to skills and orders dependencies.
- `SkillManager`: executes skills, records history, and supports parallel execution.
- Built-in skills: file, terminal, git, code, documentation, and web research.

## ARIACore Execution Path

`ARIACore` now auto-registers built-in skills through normal `SkillManager` initialization and executes typed `PlanStep` objects.

Each step produces:

- `SkillResult`
- `SkillOutcome`
- reflection update
- learning update
- episodic memory update

## Compatibility

Direct `SkillManager()` construction still starts empty by default. Built-ins are opt-in for direct users and enabled by default through `ARIACore`.

## Architectural Debt

- Permission checks are not uniformly integrated with skill execution.
- Rollback exists in skill protocols but is not yet part of a general recovery policy.
- Parallel execution is available but not yet driven by typed plan dependency groups.

## Measurement Targets

- Skill success rate.
- Skill latency.
- Validation failure rate.
- Rollback coverage.
- Recovery success after failed steps.
