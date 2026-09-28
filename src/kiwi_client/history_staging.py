"""Shared publication of immutable, separate history review bundles."""
import json
import os
from pathlib import Path
import tempfile


def write_stage(path: Path, data: dict) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            name = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(name, path)  # Exclusive publication; never overwrite a reviewed stage.
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
