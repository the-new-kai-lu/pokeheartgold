import importlib.util
from pathlib import Path
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "scripts/episode_source_inventory.py"
SPEC = importlib.util.spec_from_file_location("episode_inventory", SOURCE)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


class EpisodeInventorySafetyTests(unittest.TestCase):
    def test_relative_paths(self):
        self.assertEqual(str(inventory.safe_relative("src/map_events.c")), "src/map_events.c")
        for name in ("", "/absolute", "../escape", "a/../b", "a//b", "./a", "a\\b"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                inventory.safe_relative(name)

    def test_regular_read_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "regular").write_bytes(b"source")
            self.assertEqual(inventory.regular_bytes(root, "regular"), b"source")
            (root / "link").symlink_to(root / "regular")
            with self.assertRaises(ValueError):
                inventory.regular_bytes(root, "link")
            (root / "parent").symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                inventory.regular_bytes(root, "parent/regular")


if __name__ == "__main__":
    unittest.main()