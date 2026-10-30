from pathlib import Path

import pytest

from scripts.codegen import same_tree


@pytest.mark.parametrize("change", ["changed", "missing", "extra"])
def test_tree_comparison_rejects_drift(tmp_path, change):
    # Plain fixtures, not edits to any generated source in the repository.
    left, right = tmp_path / "left", tmp_path / "right"
    for directory in [left, right]:
        directory.mkdir()
        (directory / "fixture.py").write_text("original fixture\n")
    assert same_tree(left, right)
    if change == "changed":
        (right / "fixture.py").write_text("different fixture\n")
    elif change == "missing":
        (right / "fixture.py").unlink()
    else:
        (right / "extra.py").write_text("extra fixture\n")
    assert not same_tree(left, right)


def test_tree_comparison_ignores_only_runtime_caches(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    for directory in [left, right]:
        directory.mkdir()
        (directory / "fixture.py").write_text("same fixture\n")
    cache = right / "__pycache__"
    cache.mkdir()
    (cache / "fixture.pyc").write_bytes(b"cached runtime")
    assert same_tree(left, right)
    assert not same_tree(Path("/nonexistent-generated-tree"), right)
