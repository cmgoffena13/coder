from pathlib import Path

from src.internal.git_utils import is_git_work_tree, run_git
from src.internal.parse.db import IndexDB

DOC_NAMES = {"AGENTS.md", "pyproject.toml", "Makefile"}


def clip(text, limit=4000):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"


class WorkspaceContext:
    def __init__(
        self,
        cwd: str,
        repo_root: str,
        branch: str,
        default_branch: str,
        status: str,
        recent_commits: list[str],
        project_docs: dict[str, str],
        is_git_repo: bool,
    ):
        self.cwd = cwd
        self.repo_root = repo_root
        self.branch = branch
        self.default_branch = default_branch
        self.status = status
        self.recent_commits = recent_commits
        self.project_docs = project_docs
        self.is_git_repo = is_git_repo

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
            raise ValueError("Path escapes workspace root")
        return target

    @classmethod
    def build(cls, cwd):
        cwd = Path(cwd).resolve()
        in_git = is_git_work_tree(cwd)
        if not in_git:
            print(
                "[WARNING] Current working directory is not a git repository; "
                "git metadata during indexing and some workspace info may be unavailable."
            )

        repo_root = Path(
            run_git(cwd, ["rev-parse", "--show-toplevel"], fallback=str(cwd))
        ).resolve()
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
            branch=run_git(cwd, ["branch", "--show-current"], fallback="-") or "-",
            default_branch=(
                run_git(
                    cwd,
                    ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                    fallback="origin/main",
                )
                or "origin/main"
            ).removeprefix("origin/"),
            status=clip(
                run_git(cwd, ["status", "--short"], fallback="clean") or "clean", 1500
            ),
            recent_commits=[
                line
                for line in run_git(cwd, ["log", "--oneline", "-5"]).splitlines()
                if line
            ],
            project_docs=docs,
            is_git_repo=in_git,
        )

    def text(self):
        commits = "\n".join(f"- {line}" for line in self.recent_commits) or "- none"
        docs = (
            "\n".join(
                f"\n#### {path}\n{snippet}"
                for path, snippet in self.project_docs.items()
            )
            or "- none"
        )
        return "\n".join(
            [
                f"- cwd: {self.cwd}",
                f"- repo_root: {self.repo_root}",
                f"- branch: {self.branch}",
                f"- default_branch: {self.default_branch}",
                "- status:",
                self.status,
                "- recent_commits:",
                commits,
                self.index_overview(),
                "\n### Project Docs",
                docs,
            ]
        )

    def _detect_entry_points(self, files: list[str]) -> list[str]:
        candidates = [
            "main.py",
            "app.py",
            "server.py",
            "index.py",
            "run.py",
            "manage.py",
            "main.go",
            "main.rs",
            "index.js",
            "index.ts",
            "app.js",
            "app.ts",
            "server.js",
            "server.ts",
        ]
        found = []
        for file in files:
            basename = Path(file).name
            if basename in candidates:
                found.append(file)
        return found

    def _tests_summary(self, files: list[str], db: IndexDB) -> dict:
        test_files = [
            file for file in files if "test" in file.lower() or "spec" in file.lower()
        ]
        if not test_files:
            return {}
        test_directories = list({str(Path(file).parent) for file in test_files})
        (test_function_count,) = db.execute(
            """
            SELECT 
            COUNT(*) 
            FROM symbols 
            WHERE (name LIKE 'test_%' OR name LIKE 'Test%') 
            AND kind = 'function'
            """
        )[0]
        return {
            "files": len(test_files),
            "dirs": test_directories[:3],
            "functions": test_function_count,
        }

    def index_overview(self) -> str:
        lines: list[str] = []

        db = IndexDB(self.root)
        try:
            stats = db.stats()
            files = db.list_files()
            module_rows = db.module_summary()
            entry_points = self._detect_entry_points(files)
            test_info = self._tests_summary(files, db)

            lines.append("")
            lines.append("### Index Overview")
            lines.append(f"Project: {self.root.name}")
            lines.append(f"{stats['files']} files, {stats['symbols']} symbols")

            if stats["languages"]:
                lang_parts = [f"{lang} ({n})" for lang, n in stats["languages"].items()]
                lines.append("Languages: " + ", ".join(lang_parts))
                lines.append("")

            if module_rows:
                lines.append("Modules:")
                for row in module_rows[:15]:
                    module = row["module"] or "."
                    lines.append(
                        f"  {module} → {row['file_count']} files, {row['symbol_count']} symbols"
                    )
                lines.append("")

            if entry_points:
                lines.append("Entry points: " + ", ".join(entry_points))
                lines.append("")

            if test_info:
                lines.append(
                    f"Tests: {test_info['files']} files, {test_info['functions']} test functions"
                    + (
                        f" in {', '.join(test_info['dirs'])}"
                        if test_info.get("dirs")
                        else ""
                    )
                )
        finally:
            db.close()

        return "\n".join(lines)
