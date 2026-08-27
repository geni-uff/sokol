"""Regression: Postgres drain must import the worker as a package.

ingest_worker.py used to do `from loop import claim_next_job, process_job` while
running as a script (cwd=/app). That loaded loop as a top-level module, then
`ufdr_parser`'s `from .parsers import ...` raised ImportError, which the drain
path swallowed — jobs stayed pending forever.
"""

import ast
from pathlib import Path


def test_ingest_worker_does_not_import_bare_loop() -> None:
    src = Path(__file__).with_name("ingest_worker.py").read_text()
    tree = ast.parse(src)
    found_package_import = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        names = {alias.name for alias in node.names}
        if not {"claim_next_job", "process_job"} <= names:
            continue
        if node.module == "loop" and node.level == 0:
            raise AssertionError(
                "bare 'from loop import' loads loop as a top-level module and "
                "breaks ufdr_parser relative imports"
            )
        if node.module == "worker.loop" or (node.module == "loop" and node.level >= 1):
            found_package_import = True
    assert found_package_import, "ingest_worker must import claim_next_job from worker.loop"


def test_parser_loads_as_package() -> None:
    from worker.loop import claim_next_job, process_job
    from worker.ufdr_parser import process_ufdr

    assert callable(claim_next_job)
    assert callable(process_job)
    assert callable(process_ufdr)


if __name__ == "__main__":
    test_ingest_worker_does_not_import_bare_loop()
    test_parser_loads_as_package()
    print("ok")
