from pathlib import Path

from src.internal.git_utils import _parse_git_log_last_touch, last_commits_for_paths
from src.internal.parse.parser import INDEX_DB_BATCH_SIZE


def test_parse_git_log_last_touch_newest_wins():
    stdout = (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\t2026-01-02 00:00:00 +0000\n"
        "\n"
        "src/foo.py\n"
        "\n"
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\t2025-01-01 00:00:00 +0000\n"
        "\n"
        "src/foo.py\n"
    )
    wanted_paths = {"src/foo.py"}
    got = _parse_git_log_last_touch(stdout, wanted_paths)
    assert got["src/foo.py"][0] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert "2026-01-02" in got["src/foo.py"][1]


def test_last_commits_for_paths_on_repo():
    root = Path(__file__).resolve().parents[2]
    paths = [Path("src/internal/git_utils.py"), Path("pyproject.toml")]
    m = last_commits_for_paths(root, paths, chunk_size=INDEX_DB_BATCH_SIZE)
    for p in paths:
        h, d = m.get(p, ("", ""))
        assert len(h) == 40
        assert d
