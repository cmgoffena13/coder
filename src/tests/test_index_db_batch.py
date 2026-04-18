from pathlib import Path
from tempfile import TemporaryDirectory

from src.internal.parse.base import CallSite, ImportRef, Symbol
from src.internal.parse.db import IndexBatchItem, IndexDB


def test_apply_index_batch_writes_files_and_optional_git():
    with TemporaryDirectory() as td:
        root = Path(td)
        db = IndexDB(root)
        try:
            sym_a = Symbol(
                name="foo",
                kind="function",
                file="a.py",
                start_line=1,
                end_line=2,
                signature="foo()",
                language="python",
            )
            sym_b = Symbol(
                name="bar",
                kind="function",
                file="b.py",
                start_line=1,
                end_line=1,
                signature="bar()",
                language="python",
            )
            db.apply_index_batch(
                [
                    IndexBatchItem(
                        filepath="a.py",
                        content_hash="h1",
                        language="python",
                        line_count=10,
                        symbols=[sym_a],
                        calls=[],
                        imports=[],
                        git_commit_hash="deadbeef",
                        git_last_modified="Mon Jan 1 00:00:00 2024 +0000",
                    ),
                    IndexBatchItem(
                        filepath="b.py",
                        content_hash="h2",
                        language="python",
                        line_count=5,
                        symbols=[sym_b],
                        calls=[],
                        imports=[],
                    ),
                ]
            )
            assert db.execute("SELECT COUNT(*) AS c FROM file_meta")[0]["c"] == 2
            assert db.execute("SELECT COUNT(*) AS c FROM symbols")[0]["c"] == 2
            assert db.execute("SELECT COUNT(*) AS c FROM git_info")[0]["c"] == 1
            row = db.get_git_info(Path("a.py"))
            assert row is not None
            assert row["last_commit_hash"] == "deadbeef"
        finally:
            db.close()


def test_remove_files_batch_clears_multiple_paths():
    with TemporaryDirectory() as td:
        root = Path(td)
        db = IndexDB(root)
        try:
            s = Symbol(
                name="x",
                kind="function",
                file="x.py",
                start_line=1,
                end_line=1,
                signature="x()",
                language="python",
            )
            sym_y = Symbol(
                name="y",
                kind="function",
                file="y.py",
                start_line=1,
                end_line=1,
                signature="y()",
                language="python",
            )
            db.apply_index_batch(
                [
                    IndexBatchItem(
                        filepath="x.py",
                        content_hash="1",
                        language="python",
                        line_count=1,
                        symbols=[s],
                        calls=[
                            CallSite(
                                symbol_name="x",
                                caller_file="x.py",
                                line=1,
                                context="",
                            )
                        ],
                        imports=[
                            ImportRef(
                                symbol_name="os",
                                file="x.py",
                                import_line="import os",
                            )
                        ],
                    ),
                    IndexBatchItem(
                        filepath="y.py",
                        content_hash="2",
                        language="python",
                        line_count=1,
                        symbols=[sym_y],
                        calls=[],
                        imports=[],
                        git_commit_hash="g1",
                        git_last_modified="d1",
                    ),
                ]
            )
            db.remove_files_batch([Path("x.py"), Path("y.py")])
            assert db.execute("SELECT COUNT(*) AS c FROM file_meta")[0]["c"] == 0
            assert db.execute("SELECT COUNT(*) AS c FROM symbols")[0]["c"] == 0
            assert db.execute("SELECT COUNT(*) AS c FROM calls")[0]["c"] == 0
            assert db.execute("SELECT COUNT(*) AS c FROM imports")[0]["c"] == 0
            assert db.execute("SELECT COUNT(*) AS c FROM git_info")[0]["c"] == 0
        finally:
            db.close()


def test_apply_index_batch_empty_is_noop():
    with TemporaryDirectory() as td:
        db = IndexDB(Path(td))
        try:
            db.apply_index_batch([])
            assert db.execute("SELECT COUNT(*) AS c FROM file_meta")[0]["c"] == 0
        finally:
            db.close()
