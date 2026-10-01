import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("baseline", ROOT / "scripts/check_expansion_baseline.py")
baseline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(baseline)


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = json.loads((ROOT / "expansion/baseline.json").read_text())
        files = {
            "include/constants/maps.h", "src/data/map_headers.h", "include/map_header.h",
            "include/constants/vars.h", "include/constants/flags.h",
            *self.manifest["layout_source_sha256"],
        }
        for name in files:
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, dest)

    def replace(self, path, old, new):
        target = self.root / path
        text = target.read_text()
        self.assertIn(old, text)
        target.write_text(text.replace(old, new, 1))

    def errors(self):
        return baseline.audit(self.root, self.manifest)[0]

    def test_baseline(self):
        self.assertEqual([], self.errors())

    def test_capacity_drift(self):
        manifest = copy.deepcopy(self.manifest)
        for key in manifest["capacities"]:
            with self.subTest(key=key):
                changed = copy.deepcopy(manifest)
                changed["capacities"][key] += 1
                self.assertTrue(baseline.audit(self.root, changed)[0])

    def test_missing_header(self):
        self.replace("src/data/map_headers.h", "[MAP_EVERYWHERE]", "[UNKNOWN_MAP]")
        self.assertTrue(self.errors())

    def test_duplicate_header(self):
        self.replace("src/data/map_headers.h", "[MAP_NOTHING]", "[MAP_EVERYWHERE]")
        self.assertTrue(self.errors())

    def test_unsupported_region(self):
        self.replace("src/data/map_headers.h", ".regionNo = MAP_REGION_JOHTO", ".regionNo = MAP_REGION_HOENN")
        self.assertTrue(self.errors())

    def test_save_layout_drift(self):
        with (self.root / "include/save_vars_flags.h").open("a") as stream:
            stream.write("\n/* change requiring review */\n")
        self.assertTrue(self.errors())

    def test_nonliteral_fails_closed(self):
        with self.assertRaises(ValueError):
            baseline.literal("#define NUM_FLAGS (2912 + 8)", "NUM_FLAGS")


if __name__ == "__main__":
    unittest.main()