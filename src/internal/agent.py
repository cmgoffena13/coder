import json
from pathlib import Path
from typing import Any, Optional

from thoughtflow import AGENT, LLM, MEMORY, TOOL

from src.internal.tools.list_files import add_list_files_tool
from src.internal.tools.patch_file import add_patch_file_tool
from src.internal.tools.read_files import add_read_file_tool
from src.internal.tools.run_shell import add_run_shell_tool
from src.internal.tools.tool_search import add_search_tool
from src.internal.tools.write_file import add_write_file_tool
from src.internal.workspace import WorkspaceContext
from src.settings import config


class CoderAgent(AGENT):
    def __init__(
        self,
        workspace: WorkspaceContext,
        read_only: bool = False,
        approval_policy: str = "ask",
        depth: int = 0,
        max_depth: int = 1,
        max_steps: int = 6,
    ):
        self.name = "Coder"
        self.llm = LLM(f"ollama:{config.CODER_OLLAMA_MODEL}", think=True)
        self.workspace = workspace
        self.approval_policy = approval_policy
        self.read_only = read_only
        self.memory = None
        self.depth = depth
        self.max_depth = max_depth
        self.max_steps = max_steps
        self.system_prompt = self._load_system_prompt(workspace)
        self.tools = self._build_tools()
        super().__init__(
            name=self.name,
            llm=self.llm,
            max_iterations=self.max_steps,
            tools=self.tools,
            on_tool_call=self.approve,
            system_prompt=self.system_prompt,
        )

    def _load_system_prompt(self, workspace: WorkspaceContext) -> str:
        path = Path(__file__).resolve().parent / "system.md"
        text = path.read_text(encoding="utf-8")
        return text.replace("{workspace_text}", workspace.text())

    def _build_tools(self) -> list[TOOL]:
        tools = [
            add_list_files_tool(self.workspace),
            add_read_file_tool(self.workspace),
            add_search_tool(self.workspace),
            add_run_shell_tool(self.workspace),
            add_write_file_tool(self.workspace),
            add_patch_file_tool(self.workspace),
        ]
        if getattr(self, "depth", 0) < getattr(self, "max_depth", 1):
            tools.append(add_delegate_tool(self, self.memory))
        return tools

    def approve(self, name, args):
        if self.read_only:
            return False
        if self.approval_policy == "auto":
            return True
        if self.approval_policy == "never":
            return False
        try:
            answer = input(
                f"Approve: {name} {json.dumps(args, ensure_ascii=True)}? [y/N] "
            )
        except EOFError:
            return False
        return answer.strip().lower() in {"y", "yes"}

    # NOTE: store MEMORY in agent for delegate tool
    def __call__(self, memory: MEMORY) -> MEMORY:
        self.memory = memory
        return super().__call__(memory)


delegate_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task": {
            "type": "string",
            "description": "Task for the child agent to investigate.",
        },
        "max_steps": {
            "type": "integer",
            "description": "Maximum agent iterations for the child (default: 3).",
            "default": 3,
        },
    },
    "required": ["task"],
}


def tool_delegate(
    agent: CoderAgent, args: dict[str, Any], memory: Optional[MEMORY] = None
) -> str:
    if getattr(agent, "depth", 0) >= getattr(agent, "max_depth", 1):
        raise ValueError("delegate depth exceeded")
    task = str(args.get("task", "")).strip()
    if not task:
        raise ValueError("task must not be empty")
    max_steps = int(args.get("max_steps", 3))

    child = CoderAgent(
        workspace=agent.workspace,
        read_only=True,
    )
    child.max_iterations = max(1, max_steps)

    child_memory = MEMORY()
    # NOTE: dumb ty stuff.
    parent_msgs = (
        memory.get_msgs(limit=5, include=["user", "assistant"])
        if memory is not None
        else []
    )
    for msg in parent_msgs:
        child_memory.add_msg(role=msg["role"], content=msg["content"])
    child_memory.add_msg("user", task)
    child_memory = child(child_memory)
    answer = child_memory.last_asst_msg(content_only=True)

    tool_result = "delegate_result:\n" + answer

    return tool_result


def add_delegate_tool(agent: CoderAgent, memory: Optional[MEMORY] = None) -> TOOL:
    return TOOL(
        name="delegate",
        description="Ask a bounded read-only child agent to investigate.",
        parameters=delegate_parameters,
        fn=lambda **kwargs: tool_delegate(agent=agent, memory=memory, args=kwargs),
    )
