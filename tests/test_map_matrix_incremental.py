"""Host-only regression for the production map-matrix archive make rule."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from hgss_land import narc_members

STEM = Path("files/fielddata/mapmatrix/map_matrix")
ARCHIVE = Path(f"{STEM}.narc")
INDEX = Path(f"{STEM}.naix")


class MapMatrixIncrementalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool_dir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tool_dir.cleanup)
        source = ROOT / "tools/nitroarc"
        dest = Path(cls.tool_dir.name) / "nitroarc"
        shutil.copytree(source, dest, ignore=shutil.ignore_patterns(
            "nitroarc", "*.exe", "*.o", "*.a", "*.d"))
        subprocess.run(["make", "-C", str(dest), "nitroarc"], check=True,
                       capture_output=True, text=True)
        cls.nitroarc = dest / "nitroarc"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / STEM
        self.inputs.mkdir(parents=True)
        self.clock = time.time_ns() - 120_000_000_000

        # Use the real map_matrix.mk and the actual generic NARC recipe from
        # filesystem.mk. A fixture with a copied dependency/recipe would miss
        # the first-expansion vs stem-specific-variable interaction.
        generic = (ROOT / "filesystem.mk").read_text()
        start = generic.index("NTR_FILE_EXT := bin NCGR NCLR NCER NSCR NSBMD NSBCA NSBTA\n")
        end = generic.index("\n.PHONY: filesystem clean-filesystem clean-fs", start)
        self.assertIn(".SECONDEXPANSION:", (ROOT / "common.mk").read_text())
        harness = (".SECONDEXPANSION:\n"
                   f"NARC := {self.nitroarc}\n"
                   f"include {ROOT / 'files/fielddata/mapmatrix/map_matrix.mk'}\n"
                   + generic[start:end] + "\n")
        (self.root / "fixture.mk").write_text(harness)

        for index in range(289):
            self.write(f"map_matrix_{index:04d}.bin", bytes([index % 251]))
        self.set_time(self.inputs, self.clock)
        self.build()

    def set_time(self, path, when):
        os.utime(path, ns=(when, when))

    def write(self, name, data):
        path = self.inputs / name
        path.write_bytes(data)
        self.set_time(path, self.clock)
        return path

    def make(self, *flags):
        return subprocess.run(["make", "--no-print-directory", "-f", "fixture.mk",
                               *flags, str(ARCHIVE)], cwd=self.root,
                              capture_output=True, text=True)

    def build(self):
        result = self.make()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.set_time(self.root / ARCHIVE, self.clock + 1_000_000_000)

    def change(self, path):
        self.clock += 2_000_000_000
        self.set_time(path, self.clock)

    def assert_fresh_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            fresh = Path(temp)
            (fresh / STEM.parent).mkdir(parents=True)
            shutil.copytree(self.inputs, fresh / STEM)
            result = subprocess.run([str(self.nitroarc), "-cf", str(ARCHIVE),
                                     "--index-namespace", str(STEM)],
                                    cwd=fresh, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((self.root / ARCHIVE).read_bytes(),
                             (fresh / ARCHIVE).read_bytes())
            self.assertEqual((self.root / INDEX).read_bytes(),
                             (fresh / INDEX).read_bytes())

    def assert_rebuild(self):
        self.assertEqual(self.make("-q").returncode, 1)
        self.build()
        self.assert_fresh_pack()
        self.assert_noop()

    def assert_noop(self):
        before = ((self.root / ARCHIVE).stat().st_mtime_ns,
                  (self.root / INDEX).stat().st_mtime_ns)
        result = self.make("-q")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.make()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, ((self.root / ARCHIVE).stat().st_mtime_ns,
                                  (self.root / INDEX).stat().st_mtime_ns))

    def index_of(self, name):
        index = (self.root / INDEX).read_text()
        match = re.search(rf"^#define NARC_map_matrix_{re.escape(name[:-4])}_bin (\d+)$",
                          index, re.MULTILINE)
        self.assertIsNotNone(match, name)
        return int(match.group(1))

    def test_edit_add_rename_remove_and_append_indices(self):
        self.assert_fresh_pack()
        self.assert_noop()
        edited = self.write("map_matrix_0001.bin", b"changed fixture")
        self.change(edited)
        self.assert_rebuild()
        self.assertEqual(narc_members((self.root / ARCHIVE).read_bytes())[1],
                         b"changed fixture")

        town = self.write("map_matrix_0289_LITTLEROOT_TOWN.bin", b"town")
        self.change(self.inputs)  # a new directory entry, not a pre-existing prerequisite
        self.assert_rebuild()
        self.assertEqual(self.index_of(town.name), 289)
        route = self.write("map_matrix_0290_ROUTE_101.bin", b"route")
        self.change(self.inputs)
        self.assert_rebuild()
        self.assertEqual((self.index_of(town.name), self.index_of(route.name)),
                         (289, 290))
        self.assertEqual(narc_members((self.root / ARCHIVE).read_bytes())[-2:],
                         [b"town", b"route"])

        renamed = self.inputs / "map_matrix_0001_RENAMED.bin"
        edited.rename(renamed)
        self.change(self.inputs)
        self.assert_rebuild()
        self.assertNotIn("NARC_map_matrix_map_matrix_0001_bin ",
                         (self.root / INDEX).read_text())
        self.assertEqual(self.index_of(renamed.name), 1)

        renamed.unlink()
        self.change(self.inputs)
        self.assert_rebuild()
        self.assertEqual((self.index_of(town.name), self.index_of(route.name)),
                         (288, 289))

    def test_optional_packing_metadata(self):
        ignore = self.write(".narcignore", "map_matrix_0001.bin\n".encode())
        self.change(self.inputs)
        self.assert_rebuild()
        self.assertEqual(len(narc_members((self.root / ARCHIVE).read_bytes())), 288)

        ignore.write_text("map_matrix_0002.bin\n")
        self.change(ignore)
        self.assert_rebuild()
        self.assertEqual(self.index_of("map_matrix_0001.bin"), 1)

        ignore.unlink()
        self.change(self.inputs)
        self.assert_rebuild()
        order = self.write(".narcorder", b"map_matrix_0288.bin\n")
        self.change(self.inputs)
        self.assert_rebuild()
        self.assertEqual(self.index_of("map_matrix_0288.bin"), 0)
        order.write_text("map_matrix_0287.bin\n")
        self.change(order)
        self.assert_rebuild()
        self.assertEqual(self.index_of("map_matrix_0287.bin"), 0)
        order.unlink()
        self.change(self.inputs)
        self.assert_rebuild()
        self.assertEqual(self.index_of("map_matrix_0287.bin"), 287)