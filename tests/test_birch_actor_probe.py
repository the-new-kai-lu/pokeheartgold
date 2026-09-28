"""Private Birch binding: stock preservation, native rescue and fail-closed gates."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_birch_actor_probe import (
    ACTOR_SHA256, EVENTS, MEMBER, MMODEL, ROW, SCRIPTS, SENTINEL, SPRITES,
    SPRITE_ID, SPRITE_NAME, TABLE, audit, member_path, prepare,
)
from export_birch_actor import export as export_actor
from export_lab_model import export as export_lab
from extract_emerald_lab import extract
from hgss_land import narc_members
from stage_lab_archives import pack_narc


class BirchProbeAuditTests(unittest.TestCase):
    def test_current_source_audit(self):
        self.assertEqual(set(audit(ROOT)), {"members", "consumers", "events_scripts", "packing"})
        self.assertEqual(SPRITE_ID, 32)
        self.assertLess(SPRITE_ID, 101)
        self.assertLess(MEMBER, 65535)

    def test_drift_and_dirty_packing_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / MMODEL, root / MMODEL)
            for name in ("mmodel_00000266.NSBMD", "mmodel_00000280.json",
                         "mmodel_00000054.NSBTX"):
                with self.subTest(name=name):
                    path = root / MMODEL / name
                    original = path.read_bytes()
                    path.write_bytes(original + b"\0")
                    with self.assertRaisesRegex(ValueError, "members drift"):
                        audit(root)
                    path.write_bytes(original)
            extra = root / MMODEL / "mmodel_00000863.NSBTX"
            extra.write_bytes(b"unexpected")
            with self.assertRaisesRegex(ValueError, "count/order"):
                audit(root)
            extra.unlink()
            extra = root / MMODEL / ".narcorder"
            extra.write_text("mmodel_00000054.NSBTX\n")
            with self.assertRaisesRegex(ValueError, "packing input"):
                audit(root)

    def test_bad_actor_and_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            actor = temp / "bad.nsbtx"
            actor.write_bytes(b"not-reviewed")
            out = temp / "probe"
            with self.assertRaisesRegex(ValueError, "Unaudited Birch"):
                prepare(ROOT, temp / "missing-assets", actor, out)
            self.assertFalse(out.exists())
            out.mkdir()
            with self.assertRaisesRegex(ValueError, "existing output"):
                prepare(ROOT, temp / "missing-assets", actor, out)
            self.assertEqual(list(out.iterdir()), [])


class BirchProbeIntegrationTests(unittest.TestCase):
    def test_private_native_tree_preservation_and_archive_order(self):
        donor = Path(os.environ.get("EMERALD_DONOR", ROOT.parent / "pokeemerald"))
        if not donor.exists():
            self.skipTest("Pinned Emerald donor required")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            export_actor(ROOT, donor, temp / "actor")
            actor = temp / "actor/birch.nsbtx"
            extract(donor, temp / "pack")
            export_lab(temp / "pack", temp / "lab")
            out = temp / "probe"
            report = prepare(ROOT, temp / "lab", actor, out)
            self.assertFalse(report["RuntimeVerified"])
            self.assertFalse(report["eligibility_injected"])
            self.assertEqual(report["rescue_mode"], "native")
            self.assertEqual(report["texture_sha256"], ACTOR_SHA256)
            self.assertEqual((out / member_path()).read_bytes(), actor.read_bytes())
            self.assertEqual((out / TABLE).read_text().replace(ROW + "\n", ""),
                             (ROOT / TABLE).read_text())
            self.assertEqual((out / TABLE).read_text().count(ROW + "\n" + SENTINEL), 1)
            self.assertIn(f"#define {SPRITE_NAME} {SPRITE_ID}\n", (out / SPRITES).read_text())
            self.assertNotIn(SPRITE_NAME, (ROOT / SPRITES).read_text())
            for path in (ROOT / MMODEL).iterdir():
                self.assertEqual(path.read_bytes(), (out / MMODEL / path.name).read_bytes())
            for path in (ROOT / EVENTS).glob("*.json"):
                self.assertEqual(path.read_bytes(), (out / EVENTS / path.name).read_bytes())
            actors = json.loads((out / EVENTS / "491_HOENN_LAB_DEBUG.json").read_text())["objects"]
            self.assertEqual([(a["id"], a["spriteId"], a["x"], a["z"], a["scriptId"]) for a in actors],
                             [(0, SPRITE_NAME, 14, 17, 2),
                              (1, "SPRITE_ASSISTANTM", 18, 17, 4),
                              (2, SPRITE_NAME, 16, 17, 3)])
            entrance = (out / SCRIPTS / "scr_seq_0843_T20R0101.s").read_text()
            self.assertNotIn("SetVar 0x416e, 1", entrance)
            self.assertTrue(report["lab_overlay"]["requires_real_rescue_battle"])
            original = (ROOT / SCRIPTS / "scr_seq_0965_hoenn_reward.s").read_text()
            reward = (out / SCRIPTS / "scr_seq_0965_hoenn_reward.s").read_text()
            self.assertTrue(reward.replace("ScrDef HoennDebug_Return\n", "").startswith(original))
            # Host serialization mirrors mmodel.json.txt (u32 count,
            # all u16 timings, all u8 indices, all u8 auxiliary values).
            # Model files keep fixed-width names; extension conversion cannot
            # move any existing member or change the appended index.
            def compiled(path):
                if path.suffix != ".json":
                    return path.read_bytes()
                rows = json.loads(path.read_text())["data"]
                return (struct.pack("<I", len(rows))
                        + struct.pack("<" + "H" * len(rows), *(v["unk0"] for v in rows))
                        + bytes(v["unk1"] for v in rows) + bytes(v["unk2"] for v in rows))
            stock = [compiled(p) for p in sorted((ROOT / MMODEL).glob("mmodel_*"))]
            appended = [compiled(p) for p in sorted((out / MMODEL).glob("mmodel_*"))]
            packed = narc_members(pack_narc(appended))
            self.assertEqual(len(packed), MEMBER + 1)
            self.assertEqual(packed[:MEMBER], stock)
            self.assertEqual(hashlib.sha256(packed[MEMBER]).hexdigest(), ACTOR_SHA256)
            # A failed underlying lab stage leaves no publishable partial tree.
            failed = temp / "failed"
            with self.assertRaises(FileNotFoundError):
                prepare(ROOT, temp / "missing-assets", actor, failed)
            self.assertFalse(failed.exists())