from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import time
import traceback
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from IPython.display import display


def execute_in_process(notebook, notebook_path: Path, output_path: Path):
    """Execute cells in one Python process when a sandbox cannot open ZMQ sockets."""
    previous_cwd = Path.cwd()
    namespace = {"__name__": "__main__", "display": display}
    try:
        os.chdir(notebook_path.parent)
        for execution_count, cell in enumerate(
            (cell for cell in notebook.cells if cell.cell_type == "code"), start=1
        ):
            stdout = io.StringIO()
            stderr = io.StringIO()
            cell.outputs = []
            cell.execution_count = execution_count
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exec(
                        compile(cell.source, f"{notebook_path.name}:cell-{execution_count}", "exec"),
                        namespace,
                    )
            except Exception as exc:
                cell.outputs.append(
                    nbformat.v4.new_output(
                        "error",
                        ename=type(exc).__name__,
                        evalue=str(exc),
                        traceback=traceback.format_exc().splitlines(),
                    )
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)
                nbformat.write(notebook, output_path)
                raise
            for name, stream in (("stdout", stdout), ("stderr", stderr)):
                text = stream.getvalue()
                if text:
                    cell.outputs.append(nbformat.v4.new_output("stream", name=name, text=text))
    finally:
        os.chdir(previous_cwd)
    return notebook


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute the forecast notebook top to bottom.")
    parser.add_argument("notebook", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Execute without a Jupyter kernel (useful in restricted CI sandboxes).",
    )
    args = parser.parse_args()

    notebook_path = args.notebook.resolve()
    output_path = args.output.resolve()
    started = time.time()
    notebook = nbformat.read(notebook_path, as_version=4)
    if args.in_process:
        notebook = execute_in_process(notebook, notebook_path, output_path)
        execution_mode = "in-process"
    else:
        client = NotebookClient(
            notebook,
            timeout=args.timeout,
            kernel_name="python3",
            allow_errors=False,
            resources={"metadata": {"path": str(notebook_path.parent)}},
        )
        client.execute(cwd=str(notebook_path.parent))
        execution_mode = "jupyter-kernel"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, output_path)
    result = {
        "notebook": str(notebook_path),
        "output": str(output_path),
        "elapsed_seconds": round(time.time() - started, 3),
        "execution_mode": execution_mode,
        "code_cells": sum(cell.cell_type == "code" for cell in notebook.cells),
        "executed_code_cells": sum(
            cell.cell_type == "code" and cell.get("execution_count") is not None
            for cell in notebook.cells
        ),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
