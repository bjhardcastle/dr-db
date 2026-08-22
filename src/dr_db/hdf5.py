from __future__ import annotations

import asyncio
import urllib.parse
from pathlib import Path
from typing import Any

import lazynwb
from lazynwb._hdf5.range_reader import _BufferRangeReader
from lazynwb._hdf5.reader import (
    _default_hdf5_backend_reader,
    _HDF5BackendReader,
)

RIG_KEYS = ("/rig", "/rigName")


async def read_rig(path: str | Path) -> str | None:
    """Read the rig name from a Dynamic Routing HDF5 file.

    Dynamic Routing files use ``rigName``; ``rig`` is accepted for newer or
    normalized files. The async lazynwb HDF5 reader locates the scalar key
    through its range-backed metadata reader before the value is read.
    """
    source = str(path)
    reader = await _make_reader(source)
    try:
        entries = await reader.read_path_summary()
        rig_path = next(
            (
                entry.path
                for entry in entries
                if entry.is_dataset and entry.path in RIG_KEYS
            ),
            None,
        )
    finally:
        await reader.close()

    if rig_path is None:
        return None

    with lazynwb.file_io.FileAccessor(path) as accessor:
        value = accessor[rig_path][()]
    return _scalar_text(value)


async def _make_reader(source: str) -> _HDF5BackendReader:
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"", "file"}:
        local_path = Path(parsed.path if parsed.scheme else source)
        data = await asyncio.to_thread(local_path.read_bytes)
        return _HDF5BackendReader(
            source,
            range_reader=_BufferRangeReader(data),
        )
    return _default_hdf5_backend_reader(source)


def _scalar_text(value: Any) -> str | None:
    if hasattr(value, "item"):
        value = value.item()
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
