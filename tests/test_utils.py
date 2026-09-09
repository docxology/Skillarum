from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from skillarum.utils import (
    jsonable,
    sha256_bytes,
    sha256_json,
    sha256_text,
    stable_json,
    write_json_atomic,
    write_text_atomic,
)


def test_stable_json_hashes_and_atomic_writes(tmp_path: Path) -> None:
    value = {"b": (2, 3), "a": Path("fixture.txt")}
    assert stable_json(value) == '{"a":"fixture.txt","b":[2,3]}'
    assert sha256_json(value) == sha256_json({"a": Path("fixture.txt"), "b": (2, 3)})
    assert sha256_bytes(b"fixture") == sha256_text("fixture")
    assert jsonable(value) == {"b": [2, 3], "a": "fixture.txt"}

    text_path = tmp_path / "nested" / "value.txt"
    write_text_atomic(text_path, "first")
    write_text_atomic(text_path, "second")
    assert text_path.read_text() == "second"
    binary_path = tmp_path / "nested" / "value.bin"
    from skillarum.utils import write_bytes_atomic

    write_bytes_atomic(binary_path, b"binary")
    assert binary_path.read_bytes() == b"binary"
    json_path = tmp_path / "nested" / "value.json"
    write_json_atomic(json_path, value)
    assert json.loads(json_path.read_text()) == {"a": "fixture.txt", "b": [2, 3]}


def test_atomic_write_failure_cleans_up_temporary_payload(tmp_path: Path) -> None:
    """When the atomic os.replace fails, the temporary payload is removed."""
    from skillarum.utils import write_bytes_atomic, write_text_atomic

    def leftovers() -> list[str]:
        return [name for name in os.listdir(tmp_path) if name.endswith(".tmp")]

    text_target = tmp_path / "text-target"
    text_target.mkdir()  # a directory cannot be replaced by os.replace
    with pytest.raises(OSError):
        write_text_atomic(text_target, "content")
    assert leftovers() == []

    binary_target = tmp_path / "binary-target"
    binary_target.mkdir()
    with pytest.raises(OSError):
        write_bytes_atomic(binary_target, b"content")
    assert leftovers() == []
