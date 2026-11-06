import ast
from pathlib import Path


def test_application_never_imports_a_synchronous_postgres_driver():
    forbidden = {"psycopg", "psycopg2", "pg8000"}
    root = Path(__file__).resolve().parents[1] / "app"
    for path in root.rglob("*.py"):
        if "generated" in path.relative_to(root).parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            assert not any(name.split(".")[0] in forbidden for name in names), path
