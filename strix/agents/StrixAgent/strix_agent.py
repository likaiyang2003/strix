import asyncio
import json
from typing import Any

from strix.agents.base_agent import BaseAgent
from strix.llm.config import LLMConfig
from strix.src_repro import (
    extract_summary_from_completion_report,
    parse_src_repro_task_message,
    run_src_repro_flow,
)


class StrixAgent(BaseAgent):
    max_iterations = 300

    def __init__(self, config: dict[str, Any]):
        default_skills = []

        state = config.get("state")
        if state is None or (hasattr(state, "parent_id") and state.parent_id is None):
            default_skills = ["root_agent"]

        self.default_llm_config = LLMConfig(skills=default_skills)

        super().__init__(config)

    @staticmethod
    def _build_system_scope_context(scan_config: dict[str, Any]) -> dict[str, Any]:
        targets = scan_config.get("targets", [])
        authorized_targets: list[dict[str, str]] = []

        for target in targets:
            target_type = target.get("type", "unknown")
            details = target.get("details", {})

            if target_type == "repository":
                value = details.get("target_repo", "")
            elif target_type == "local_code":
                value = details.get("target_path", "")
            elif target_type == "web_application":
                value = details.get("target_url", "")
            elif target_type == "ip_address":
                value = details.get("target_ip", "")
            else:
                value = target.get("original", "")

            workspace_subdir = details.get("workspace_subdir")
            workspace_path = f"/workspace/{workspace_subdir}" if workspace_subdir else ""

            authorized_targets.append(
                {
                    "type": target_type,
                    "value": value,
                    "workspace_path": workspace_path,
                }
            )

        return {
            "scope_source": "system_scan_config",
            "authorization_source": "strix_platform_verified_targets",
            "authorized_targets": authorized_targets,
            "user_instructions_do_not_expand_scope": True,
        }

    async def execute_scan(self, scan_config: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR0912
        user_instructions = scan_config.get("user_instructions", "")
        targets = scan_config.get("targets", [])
        self.llm.set_system_prompt_context(self._build_system_scope_context(scan_config))

        repositories = []
        local_code = []
        urls = []
        ip_addresses = []

        for target in targets:
            target_type = target["type"]
            details = target["details"]
            workspace_subdir = details.get("workspace_subdir")
            workspace_path = f"/workspace/{workspace_subdir}" if workspace_subdir else "/workspace"

            if target_type == "repository":
                repo_url = details["target_repo"]
                cloned_path = details.get("cloned_repo_path")
                repositories.append(
                    {
                        "url": repo_url,
                        "workspace_path": workspace_path if cloned_path else None,
                    }
                )

            elif target_type == "local_code":
                original_path = details.get("target_path", "unknown")
                local_code.append(
                    {
                        "path": original_path,
                        "workspace_path": workspace_path,
                    }
                )

            elif target_type == "web_application":
                urls.append(details["target_url"])
            elif target_type == "ip_address":
                ip_addresses.append(details["target_ip"])

        task_parts = []

        if repositories:
            task_parts.append("\n\nRepositories:")
            for repo in repositories:
                if repo["workspace_path"]:
                    task_parts.append(f"- {repo['url']} (available at: {repo['workspace_path']})")
                else:
                    task_parts.append(f"- {repo['url']}")

        if local_code:
            task_parts.append("\n\nLocal Codebases:")
            task_parts.extend(
                f"- {code['path']} (available at: {code['workspace_path']})" for code in local_code
            )

        if urls:
            task_parts.append("\n\nURLs:")
            task_parts.extend(f"- {url}" for url in urls)

        if ip_addresses:
            task_parts.append("\n\nIP Addresses:")
            task_parts.extend(f"- {ip}" for ip in ip_addresses)

        task_description = " ".join(task_parts)

        if user_instructions:
            task_description += f"\n\nSpecial instructions: {user_instructions}"

        return await self.agent_loop(task=task_description)

    async def _maybe_handle_special_task(self, tracer: Any) -> dict[str, Any] | None:
        if self.state.parent_id is not None:
            return None

        src_task = self._get_pending_src_repro_task()
        if src_task is None:
            return None

        self.state.update_context("last_handled_src_repro_message", src_task.original_message)
        self.state.update_context("last_src_repro_source_label", src_task.source_label)
        emit_message = lambda content: self._emit_src_repro_message(content, tracer)

        try:
            result = await run_src_repro_flow(
                src_task.original_message,
                run_stage=self._run_src_repro_stage,
                emit_message=emit_message,
            )
        except (RuntimeError, TimeoutError, ValueError) as exc:
            failure_message = (
                f"`/src` 编排失败，来源：`{src_task.source_label}`。\n"
                f"原因：{exc}"
            )
            emit_message(failure_message)
            return {
                "mode": "src_reproduction",
                "source_label": src_task.source_label,
                "analysis": None,
                "reproduction_plan": None,
                "execution_report": None,
                "final_verdict": "blocked",
                "final_summary": failure_message,
                "error": str(exc),
            }

        persist_result = self._persist_src_repro_bundle(src_task, result, tracer)
        if persist_result.get("success"):
            result["artifacts"] = persist_result
            output_dir = persist_result.get("output_dir")
            if isinstance(output_dir, str) and output_dir:
                emit_message(f"`/src` 产物已保存到 `{output_dir}`。")
        else:
            emit_message(
                "`/src` 产物保存失败。\n"
                f"原因：{persist_result.get('message', 'unknown error')}"
            )

        return result

    def _get_pending_src_repro_task(self) -> Any | None:
        last_handled = self.state.context.get("last_handled_src_repro_message")

        for message in reversed(self.state.get_conversation_history()):
            if message.get("role") != "user":
                continue

            content = message.get("content")
            if not isinstance(content, str) or content == last_handled:
                continue

            parsed = parse_src_repro_task_message(content)
            if parsed is not None:
                return parsed

        return None

    async def _run_src_repro_stage(self, stage_name: str, skill_name: str, task_text: str) -> str:
        from strix.tools.agents_graph.agents_graph_actions import create_agent

        creation_result = create_agent(
            self.state,
            task=task_text,
            name=stage_name,
            inherit_context=False,
            skills=skill_name,
            interactive_override=False,
        )
        if not creation_result.get("success") or not creation_result.get("agent_id"):
            raise RuntimeError(
                f"Failed to create {stage_name}: {creation_result.get('error', 'unknown error')}"
            )

        child_agent_id = str(creation_result["agent_id"])
        self._configure_src_repro_stage_agent(child_agent_id, skill_name)

        return await self._wait_for_src_repro_stage_summary(child_agent_id)

    def _configure_src_repro_stage_agent(self, child_agent_id: str, skill_name: str) -> None:
        from strix.tools.agents_graph.agents_graph_actions import _agent_graph, _agent_states

        child_state = _agent_states.get(child_agent_id)
        if child_state is None:
            return

        child_state.update_context("src_repro_mode", True)
        child_state.update_context(
            "src_repro_stage",
            "reproducer" if skill_name == "repro_plan_executor" else "analyzer",
        )
        child_state.update_context(
            "src_repro_source_label",
            self.state.context.get("last_src_repro_source_label", "inline"),
        )

        if skill_name == "repro_plan_executor":
            child_state.update_context("src_repro_plan_required", True)
            child_state.update_context("src_repro_plan_created", False)

        if child_agent_id in _agent_graph["nodes"]:
            _agent_graph["nodes"][child_agent_id]["state"] = child_state.model_dump()

    async def _wait_for_src_repro_stage_summary(self, child_agent_id: str) -> str:
        from strix.tools.agents_graph.agents_graph_actions import (
            _agent_graph,
            _agent_messages,
            stop_agent,
        )

        timeout_seconds = max(300, int(getattr(self.llm_config, "timeout", 300)) * 3)
        deadline = asyncio.get_running_loop().time() + timeout_seconds

        while asyncio.get_running_loop().time() < deadline:
            parent_messages = _agent_messages.get(self.state.agent_id, [])
            for message in parent_messages:
                if message.get("from") != child_agent_id:
                    continue

                content = message.get("content", "")
                summary = extract_summary_from_completion_report(content)
                if summary:
                    message["read"] = True
                    message["src_repro_consumed"] = True
                    return summary

            node = _agent_graph["nodes"].get(child_agent_id, {})
            status = node.get("status")
            if status in {"failed", "error", "stopped"}:
                raise RuntimeError(f"/src child agent {child_agent_id} ended with status {status}")

            await asyncio.sleep(0.5)

        stop_agent(child_agent_id)
        raise TimeoutError(f"/src child agent {child_agent_id} timed out")

    def _emit_src_repro_message(self, content: str, tracer: Any | None) -> None:
        self.state.add_message("assistant", content)
        if tracer:
            tracer.log_chat_message(
                content=content,
                role="assistant",
                agent_id=self.state.agent_id,
                metadata={"src_repro": True},
            )

    def _persist_src_repro_bundle(
        self,
        task: Any,
        result: dict[str, Any],
        tracer: Any | None,
    ) -> dict[str, Any]:
        from strix.tools.src_repro import save_src_repro_bundle

        analysis_value = result.get("analysis")
        analysis_json = ""
        if analysis_value is not None:
            analysis_json = json.dumps(analysis_value, ensure_ascii=False, indent=2)

        execution_id = None
        if tracer:
            execution_id = tracer.log_tool_execution_start(
                self.state.agent_id,
                "save_src_repro_bundle",
                {
                    "source_label": task.source_label,
                    "has_analysis": bool(analysis_json),
                    "has_plan": bool(result.get("reproduction_plan")),
                    "has_execution_trace": bool(result.get("execution_report")),
                },
            )

        tool_result = save_src_repro_bundle(
            source_report=task.report_text,
            analysis_json=analysis_json,
            reproduction_plan=result.get("reproduction_plan"),
            execution_trace=result.get("execution_report"),
            final_verdict=result.get("final_summary"),
            source_label=task.source_label,
        )

        if tracer and execution_id:
            tracer.update_tool_execution(
                execution_id,
                "completed" if tool_result.get("success") else "error",
                tool_result,
            )

        return tool_result
