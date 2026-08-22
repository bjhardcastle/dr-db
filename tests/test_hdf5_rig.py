from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest import TestCase

import h5py

from dr_db.hdf5 import read_rig


class HDF5RigTests(TestCase):
    def test_reads_rig_name_from_different_file_vintages(self) -> None:
        fixtures = {
            "early": ("rigName", b"E1"),
            "middle": ("rigName", b"B1"),
            "recent": ("rig", b"BEH.E"),
        }

        with tempfile.TemporaryDirectory() as directory:
            for vintage, (key, expected) in fixtures.items():
                path = Path(directory) / f"{vintage}.hdf5"
                with h5py.File(path, "w") as file:
                    file.create_dataset(key, data=expected)
                    file.create_dataset("unrelated_data", data=[1, 2, 3])

                self.assertEqual(
                    expected.decode(),
                    asyncio.run(read_rig(path)),
                    vintage,
                )

    def test_returns_none_when_rig_key_is_missing(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".hdf5") as temporary:
            with h5py.File(temporary.name, "w") as file:
                file.create_dataset("not_rig", data=b"E1")

            self.assertIsNone(asyncio.run(read_rig(temporary.name)))
