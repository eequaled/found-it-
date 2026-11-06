from unittest.mock import patch

from scripts import codegen


def test_validate_runs_sqlc_compile():
    with patch("scripts.codegen.subprocess.run") as run:
        codegen.validate()
    assert run.call_args.args[0][1] == "compile"


def test_generate_runs_sqlc_generate():
    with patch("scripts.codegen.subprocess.run") as run:
        codegen.generate()
    assert run.call_args.args[0][1] == "generate"
    assert run.call_args.kwargs["cwd"] == codegen.ROOT
