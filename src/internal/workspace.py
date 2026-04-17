import subprocess
from pathlib import Path

DOC_NAMES = {"AGENTS.md", "README.md", "pyproject.toml", "Makefile"}


def clip(text, limit=4000):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


class WorkspaceContext:
    def __init__(
        self,
        cwd,
        repo_root,
        branch,
        default_branch,
        status,
        recent_commits,
        project_docs,
    ):
        self.cwd = cwd
        self.repo_root = repo_root
        self.branch = branch
        self.default_branch = default_branch
        self.status = status
        self.recent_commits = recent_commits
        self.project_docs = project_docs

    @property
    def root(self) -> Path:
        """Absolute repo root; tools use this for cwd and path resolution."""
        return Path(self.repo_root)

    def path(self, rel: str) -> Path:
        """Resolve ``rel`` (relative to repo root) to an absolute path under ``root``."""
        rel = str(rel).strip() or "."
        base = self.root.resolve()
        target = (base / rel).resolve()
        if not target.is_relative_to(base):
            raise ValueError("path escapes workspace root")
        return target

    @classmethod
    def build(cls, cwd):
        cwd = Path(cwd).resolve()

        def git(args, fallback=""):
            try:
                result = subprocess.run(
                    ["git", *args],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5,
                )
                return result.stdout.strip() or fallback
            except Exception:
                return fallback

        repo_root = Path(git(["rev-parse", "--show-toplevel"], str(cwd))).resolve()
        docs = {}
        for base in (repo_root, cwd):
            for name in DOC_NAMES:
                path = base / name
                if not path.exists():
                    continue
                key = str(path.relative_to(repo_root))
                if key in docs:
                    continue
                docs[key] = clip(
                    path.read_text(encoding="utf-8", errors="replace"), 1200
                )

        return cls(
            cwd=str(cwd),
            repo_root=str(repo_root),
            branch=git(["branch", "--show-current"], "-") or "-",
            default_branch=(
                git(
                    ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                    "origin/main",
                )
                or "origin/main"
            ).removeprefix("origin/"),
            status=clip(git(["status", "--short"], "clean") or "clean", 1500),
            recent_commits=[
                line for line in git(["log", "--oneline", "-5"]).splitlines() if line
            ],
            project_docs=docs,
        )

    def text(self):
        commits = "\n".join(f"- {line}" for line in self.recent_commits) or "- none"
        docs = (
            "\n".join(
                f"- {path}\n{snippet}" for path, snippet in self.project_docs.items()
            )
            or "- none"
        )
        return "\n".join(
            [
                "Workspace:",
                f"- cwd: {self.cwd}",
                f"- repo_root: {self.repo_root}",
                f"- branch: {self.branch}",
                f"- default_branch: {self.default_branch}",
                "- status:",
                self.status,
                "- recent_commits:",
                commits,
                "- project_docs:",
                docs,
            ]
        )
