---
name: report-to-repro-checklist
description: Convert a plain-text vulnerability report plus analyzer output into a structured reproduction checklist for /src mode
---

# Report To Repro Checklist

## Goal

Transform the provided vulnerability report into an execution-ready reproduction checklist.

This skill only converts report text into steps.
It does not re-evaluate whether the report is reproducible.

## Hard Constraints

- Respect the analyzer decision already provided by the parent agent
- Do not re-judge `can_reproduce`
- Do not invent credentials, tokens, payloads, bypasses, headers, or exploit chains absent from the report
- Preserve the original report order whenever the report implies a sequence
- Keep every step atomic and executable
- Prefer using Strix-native tools such as browser, proxy, terminal, and python when suggesting tooling
- Do not output old external tool names such as `/playwright-cli`, `/http-replay`, `/traffic-capture`, `/evidence-capture`, or `/web-login`
- Do not output browser actions that do not exist in the current project, such as `browser_action (screenshot)`
- Do not spread raw passwords, tokens, cookies, API keys, or verification codes into the plan; refer to them by the original field name from the report

## Allowed Suggested Tools

Only use these exact tool names in `Suggested Tool`:

- `browser_action`
- `send_request`
- `repeat_request`
- `list_requests`
- `view_request`
- `python`
- `terminal`

Prefer a single primary tool. Only include a secondary tool when the report clearly requires both.

### Tool Routing

- UI navigation, open page, click, input, wait, view source, or collect browser console state: `browser_action`
- Direct API write, replay, or response validation: `send_request`
- Reusing a previously captured request with modifications: `repeat_request`
- Finding or reviewing captured requests: `list_requests` or `view_request`
- Structured response parsing, token decoding, field comparison, or small helper logic: `python`
- Shell-only behavior with no better project-native alternative: `terminal`

## Required Output Shape

Return a structured checklist with exactly these sections in this order:

## Extracted Facts

- `Target System`
- `Target Host/IP`
- `Entry URL / Endpoint`
- `Account / Credential References`
- `Critical Path`
- `Vulnerability Type / Category`
- `Expected Impact`
- `Original Conclusion`
- `Analyzer Summary`

## Preconditions

- `Environment`
- `Account / Credential References`
- `Access Requirements`
- `Sensitive Field Handling`

## Detailed Reproduction Steps

For every step, use this shape:

1. `Step Name`
   - `Objective`:
   - `Exact Operation`:
   - `Expected Evidence`:
   - `Suggested Tool`:

Repeat for as many steps as needed.

## Success Criteria

- `Success Marker`
- `Stop Conditions`

## Evidence Checklist

- list the concrete screenshots, responses, fields, or observations that should be collected

## Planning Rules

- If the report mixes UI navigation and request replay, preserve the report order unless the report already gives a concrete API endpoint, method, body, and success response that should be validated first
- If a value is clearly present in the report, carry it forward
- If a high-risk secret appears in the report, refer to it as a credential reference rather than spreading it unnecessarily
- If a step depends on context that is only implied, mark it as an explicit assumption inside that step instead of inventing extra attack logic
- If the report already gives a concrete API endpoint, method, request body, and validation response, prefer an API-first plan:
  - establish only the minimum session context needed
  - send or replay the request
  - validate the response
  - use UI steps only for the final trigger or visual confirmation
- Do not create open-ended page exploration steps
- Do not create DOM hunting steps
- Do not turn "find the page" into a broad browsing task; use only the entry, menu, or route chain explicitly given by the report
- Keep sensitive values redacted:
  - keep usernames, URLs, endpoints, field names, and menu paths if they are not secrets
  - do not print raw password, token, cookie, or API key values
  - write `report-provided Authorization header`, `report-provided Cookie`, `report-provided jwt-token`, or equivalent field-name references instead
- The final step MUST be a concrete evidence collection step such as `Collect Final Verification Evidence`
- The stop condition must be tied to the final validation/evidence step:
  - once the final validation step completes without the success marker, stop the current reproduction flow immediately
  - do not continue into adjacent pages, menus, tabs, or similar features

## Role-Aware Planning Rules

- Preserve the analyzer's role distinction between current prerequisites, historical packet evidence, success markers, and post-exploitation results
- Only put current `execution_prerequisite` items into `## Preconditions`
- Do not place `historical_packet_evidence` in `## Preconditions`
- Do not place `post_exploitation_result` in `## Preconditions`
- Do not place `success_marker` items in `## Preconditions`
- Historical packets, headers, cookies, tokens, or checksums from the report may appear in `## Extracted Facts` or in a bounded replay step as report evidence, but not as implied live credentials
- If the report only shows a previously captured packet, describe it as `report-described historical request shape`, `report-described historical headers`, or equivalent language unless current reuse is explicitly proven
- If the report says that a trigger leaks a token, cookie, session ID, account data, or other sensitive value, keep that only in `Expected Impact`, `Success Criteria`, the final validation step, or `Evidence Checklist`
- Do not instruct the executor to use `report-provided jwt-token`, `report-provided Cookie`, or similar values unless the report explicitly states they are still valid and intended for current reuse
- If the report shows a historically logged-in state but does not explain how a new tester obtains that state now, keep that as a bounded prerequisite or assumption; do not silently erase it
- `Authorization: bearer null`, empty tokens, placeholder headers, or similar packet details may be copied as request-shape evidence when relevant, but must not be used by the planner as independent proof that authentication is unnecessary
- If the analyzer concluded that reproduction is possible without reusable auth material, keep Preconditions minimal and do not reintroduce leaked or historical secrets into the plan
- When the success condition is data leakage, describe the class of leaked data in prose rather than treating the exact report-shown secret value as an input requirement

## Step Construction Guidance

- UI-only verification issues:
  - use `browser_action` for entry, click, input, and final observation
- API-heavy issues:
  - use `send_request` or `repeat_request` as the primary execution path
  - use `browser_action` only when session establishment or final UI confirmation is necessary
- Mixed UI + API issues:
  - keep the minimum UI needed to reach the authenticated state or target feature
  - prefer the API write or replay step as the central validation step
  - keep final UI confirmation bounded and explicit

## Subagent Finish Contract

If you are running as a child agent, put the entire checklist into `agent_finish.result_summary`.
