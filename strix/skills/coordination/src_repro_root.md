---
name: src-repro-root
description: Serial report-driven /src orchestration for analyzer -> planner -> reproducer without generic recon or scan expansion
---

# /src Root Orchestration

This skill is only active when the current task contains `<src_repro_task>` and
`<mode>src_reproduction</mode>`.

When active, this skill OVERRIDES the generic root-agent workflow.

## Mission

Coordinate a strict report-driven reproduction flow:

1. Analyzer determines whether the report can be reproduced
2. Planner converts the report into structured reproduction steps
3. Reproducer executes the approved plan with Strix tools

Treat `<report_text>` as the only source of truth for the vulnerability details.

## Hard Constraints

- Do not perform broad reconnaissance, generic crawling, generic vulnerability scanning, or unrelated validation
- Do not create reporting agents or fixing agents in `/src` mode
- Do not skip analyzer or planner
- Do not run analyzer, planner, and reproducer in parallel
- Keep exactly one active child stage at a time
- Do not invent persistence tools that are not currently available

## Stage 1: Analyzer

Create one child agent with:

- Name: `SRC Repro Analyzer`
- Skills: `report_repro_analyzer`
- Responsibility: decide only `can_reproduce`, `reason`, and `missing_info`

The delegated task should explicitly instruct the child to:

- analyze only reproducibility readiness
- avoid execution, planning, recon, or tool usage unless absolutely needed for reading context
- return strict JSON only
- place the exact final JSON string into `agent_finish.result_summary`

After creating the analyzer child:

- call `wait_for_message`
- parse the incoming `<agent_completion_report>`
- read the analyzer JSON from the `<summary>` field

If analyzer result says `can_reproduce=false`:

- stop the `/src` workflow immediately
- do not create planner or reproducer
- finish with a concise root-level summary that preserves the analyzer reason and missing info

## Stage 2: Planner

Only start this stage when analyzer returned `can_reproduce=true`.

Create one child agent with:

- Name: `SRC Repro Planner`
- Skills: `report_to_repro_checklist`
- Responsibility: convert the report and analyzer result into structured reproduction steps

The delegated task should explicitly instruct the child to:

- preserve the original report order
- avoid re-judging reproducibility
- avoid inventing credentials, payloads, bypasses, or exploit chains absent from the report
- put the full reproduction checklist into `agent_finish.result_summary`

After creating the planner child:

- call `wait_for_message`
- parse the incoming `<agent_completion_report>`
- read the full structured plan from the `<summary>` field

## Stage 3: Reproducer

Create one child agent with:

- Name: `SRC Reproducer`
- Skills: `repro_plan_executor`
- Responsibility: execute the plan exactly as written

The delegated task should explicitly instruct the child to:

- use the original report and planner output together
- execute the plan in order with available browser, proxy, terminal, and python tools
- avoid redesigning the plan
- place the final execution report into `agent_finish.result_summary`

After creating the reproducer child:

- call `wait_for_message`
- parse the incoming `<agent_completion_report>`
- read the final execution report from the `<summary>` field

## Root Finalization

When all required stages are complete:

- summarize the analyzer decision
- summarize the planner output
- summarize the reproducer verdict or the early analyzer stop reason
- finish the root task with `finish_scan`

Use the four `finish_scan` fields in a `/src`-specific way:

- `executive_summary`: final `/src` verdict and one-paragraph outcome
- `methodology`: serial `analyzer -> planner -> reproducer` workflow
- `technical_analysis`: analyzer JSON, planner checklist summary, reproducer execution summary
- `recommendations`: missing information, blockers, or next actions
