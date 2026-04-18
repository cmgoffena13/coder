import json
from pathlib import Path
from typing import Any, Optional

from thoughtflow import AGENT, LLM, MEMORY, TOOL

from src.internal.parse.index_read import DiffLedger
from src.internal.tools import (
    add_index_read_tool,
    add_index_resolve_tool,
    add_index_search_tool,
    add_index_task_memory_tool,
    add_list_files_tool,
    add_patch_file_tool,
    add_read_file_tool,
    add_run_shell_tool,
    add_search_tool,
    add_write_file_tool,
)
from src.internal.workspace import WorkspaceContext
from src.settings import config

TOOL_APPROVAL = {
    "list_files": "safe",
    "read_file": "safe",
    "search": "safe",
    "run_shell": "approval required",
    "write_file": "approval required",
    "patch_file": "approval required",
    "index_read": "safe",
    "index_resolve": "safe",
    "index_search": "safe",
    "index_task_memory": "safe",
    "delegate": "safe",
}


class CoderAgent(AGENT):
    def __init__(
        self,
        workspace: WorkspaceContext,
        read_only: bool = False,
        approval_policy: str = "balanced",
        depth: int = 0,
        max_depth: int = 1,
        max_steps: int = 10,
        verbose: bool = False,
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
        self.verbose = verbose
        self.diff_ledger = DiffLedger()
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
        v = self.verbose
        tools = [
            add_list_files_tool(self.workspace, v),
            add_read_file_tool(self.workspace, v),
            add_search_tool(self.workspace, v),
            add_run_shell_tool(self.workspace, v),
            add_write_file_tool(self.workspace, v),
            add_patch_file_tool(self.workspace, v),
            add_index_read_tool(self.workspace, self.diff_ledger, v),
            add_index_resolve_tool(self.workspace, v),
            add_index_search_tool(self.workspace, v),
            add_index_task_memory_tool(self.workspace, v),
        ]
        if getattr(self, "depth", 0) < getattr(self, "max_depth", 1):
            tools.append(add_delegate_tool(self, self.memory, v))
        return tools

    def approve(self, name, args):
        if self.read_only:
            return False
        if self.approval_policy == "balanced":
            if TOOL_APPROVAL.get(name, "approval required") == "safe":
                return True
        if self.approval_policy == "never":
            return False
        try:
            answer = input(
                f"\nApprove: {name} {json.dumps(args, ensure_ascii=True)}? [y/N] "
            )
        except EOFError:
            return False
        return answer.strip().lower() in {"y", "yes"}

    # NOTE: store MEMORY in agent for delegate tool
    def __call__(self, memory: MEMORY) -> MEMORY:
        self.memory = memory
        if getattr(self, "depth", 0) == 0:
            self.diff_ledger.next_turn()
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
    agent: CoderAgent,
    args: dict[str, Any],
    memory: Optional[MEMORY] = None,
    verbose: bool = False,
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
    if verbose:
        print(f"[DELEGATE] {tool_result}")
    return tool_result


def add_delegate_tool(
    agent: CoderAgent, memory: Optional[MEMORY] = None, verbose: bool = False
) -> TOOL:
    return TOOL(
        name="delegate",
        description="Ask a bounded read-only child agent to investigate.",
        parameters=delegate_parameters,
        fn=lambda **kwargs: tool_delegate(
            agent=agent, memory=memory, args=kwargs, verbose=verbose
        ),
    )
