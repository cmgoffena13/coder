import pytest


@pytest.fixture(autouse=True)
def isolated_parse_index_dir(tmp_path, monkeypatch):
    """Route parse-index SQLite files into pytest's tmp_path, not repo .parse_index/."""
    idx_dir = tmp_path / "parse_index"
    idx_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "src.internal.parse.db.get_index_storage_dir",
        lambda: idx_dir,
    )
