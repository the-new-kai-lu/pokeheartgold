"""Synthetic donor source fixtures; no ROMs, assets, or game execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import census_campaign_state as census


class CensusTests(unittest.TestCase):
    def test_expression_rejects_code(self):
        self.assertEqual(census.expression("(BASE + 3) - 1", {"BASE": 4}), 6)
        self.assertEqual(census.expression("0x91f + (8 - 0x91f % 8)", {}), 0x920)
        with self.assertRaises((ValueError, SyntaxError)):
            census.expression("__import__('os').system('false')", {})
        with self.assertRaises(ValueError):
            census.expression("1 % 0", {})

    def test_synthetic_closure_and_determinism(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            emerald = root / "emerald"
            platinum = root / "platinum"
            scope = root / "scope.json"
            def put(base, path, value):
                dest = base / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(value)
            subprocess.run(["git", "init", "-q", str(emerald)], check=True)
            subprocess.run(["git", "init", "-q", str(platinum)], check=True)
            # git rev-parse HEAD requires one actual commit in each synthetic checkout.
            for base in (emerald, platinum):
                subprocess.run(["git", "-C", str(base), "-c", "user.name=fixture",
                                "-c", "user.email=fixture@example.invalid",
                                "commit", "--allow-empty", "-qm", "fixture"], check=True)
            put(emerald, "include/constants/opponents.h", "#define TRAINER_ONE 2\n")
            put(emerald, "include/constants/flags.h",
                "#define FLAG_ONE 0x40\n#define FLAG_TEMP_1 1\n"
                "#define DAILY_FLAGS_START (0x91f + (8 - 0x91f % 8))\n"
                "#define FLAG_DAILY_FLOWER_SHOP_RECEIVED_BERRY (DAILY_FLAGS_START + 0x10)\n")
            put(emerald, "include/constants/vars.h",
                "#define VAR_ONE 0x4011\n#define VAR_0x8000 0x8000\n")
            put(emerald, "data/maps/Test/map.json", json.dumps({
                "object_events": [{"script": "Test_Start", "flag": "FLAG_ONE"}]}))
            put(emerald, "data/maps/Test/scripts.inc",
                "Test_Start::\nsetflag FLAG_ONE\nsetvar VAR_ONE, 1\n"
                "goto_if_set FLAG_ONE, Shared_Run\n"
                "goto_if_eq VAR_ONE, 1, Shared_Run\n"
                "setvar VAR_0x8000, 2\ncall Shared_Run\nend\n")
            put(emerald, "data/scripts/shared.inc",
                "Shared_Run::\nswitch VAR_0x8000\ncase 1, Shared_Case\n"
                "special UnresolvedCFunction\nreturn\n"
                "Shared_Case::\nsettrainerflag TRAINER_ONE\n"
                "setflag FLAG_DAILY_FLOWER_SHOP_RECEIVED_BERRY\nreturn\n")
            put(platinum, "generated/vars_flags.txt",
                "FLAG_UNUSED_0x0000\nMAP_LOCAL_FLAGS_START\n"
                "FLAG_MAP_LOCAL_0x01 = MAP_LOCAL_FLAGS_START\n"
                "FLAG_REAL = 65\nVARS_START = 16384\n"
                "MAP_LOCAL_VARS_START = VARS_START\n"
                "VAR_REAL = 16416\nSCRIPT_LOCAL_VARS_START = 32768\n"
                "VAR_0x8000 = SCRIPT_LOCAL_VARS_START\n"
                "HIDDEN_ITEM_FLAGS_START = 730\n"
                "FLAG_OBTAINED_HIDDEN_TEST = HIDDEN_ITEM_FLAGS_START\n")
            put(platinum, "generated/trainers.txt", "TRAINER_NONE\nTRAINER_ONE\n")
            put(platinum, "res/field/events/events_test.json",
                json.dumps({"object_events": [{"hidden_flag": "FLAG_REAL",
                                                 "script": "TRAINER_ONE"}],
                            "bg_events": [{"script": 8000}, {"script": 9999}]}))
            put(platinum, "res/field/scripts/scripts_test.s",
                "    ScriptEntry Start\nStart:\n    SetVar VAR_REAL, 2\n"
                "    GoToIfEq VAR_REAL, TRUE, Start\n"
                "    SetFlag FLAG_REAL\n    SetTrainerFlag TRAINER_ONE\n"
                "    Common_CallNurse LOCALID_NURSE\n"
                "    Common_GiveItemQuantity\n    End\n")
            put(platinum, "res/field/scripts/scripts_common.s",
                "    ScriptEntry Nurse @ 0x7D2\n"
                "    ScriptEntry ItemScript @ 0x7E0\n"
                "Nurse:\n    SetFlag FLAG_REAL\n    End\n"
                "ItemScript:\n    End\n")
            put(platinum, "asm/macros/scrcmd.inc",
                "    .macro Common_CallNurse nurse\n"
                "    CallCommonScript 0x7D2\n    .endm\n"
                "    .macro Common_GiveItemQuantity\n"
                "    CallCommonScript 0x7E0\n    .endm\n")
            put(platinum, "include/script_manager.h",
                "#define SCRIPT_ID_OFFSET_COMMON_SCRIPTS 2000\n"
                "#define SCRIPT_ID_OFFSET_BG_EVENTS 2500\n"
                "#define SCRIPT_ID_OFFSET_HIDDEN_ITEMS 8000\n"
                "#define SCRIPT_ID_OFFSET_SAFARI_GAME 8800\n")
            put(platinum, "src/script_manager.c",
                "if (scriptID >= SCRIPT_ID_OFFSET_HIDDEN_ITEMS && "
                "scriptID <= SCRIPT_ID_OFFSET_SAFARI_GAME - 1) {}\n"
                "return scriptID - SCRIPT_ID_OFFSET_HIDDEN_ITEMS + HIDDEN_ITEM_FLAGS_START;\n"
                "FieldSystem_CheckFlag(fieldSystem, Script_GetHiddenItemFlag(bgEvents[eventIndex].script));\n"
                "ScriptManager_SetHiddenItem(scriptManager, scriptID);\n"
                "Entry(SCRIPT_ID_OFFSET_COMMON_SCRIPTS, scripts_common, text);\n")
            scope.write_text(json.dumps({
                "schema_version": 1, "scope": "test",
                "emerald": {"maps": ["Test"], "selection": "synthetic",
                            "badge_evidence": "data/maps/Test/scripts.inc"},
                "platinum": {"maps": ["test"], "selection": "synthetic",
                             "badge_evidence": "res/field/scripts/scripts_test.s"}}))
            output = census.report(emerald, platinum, scope)
            self.assertEqual(json.dumps(output, sort_keys=True),
                             json.dumps(census.report(emerald, platinum, scope), sort_keys=True))
            self.assertFalse(output["reachability_proven"])
            self.assertEqual(output["donors"]["emerald"]["resolved_saved_reference_counts"],
                             {"flag": 2, "variable": 1, "trainer_defeat": 1})
            self.assertEqual(output["donors"]["platinum"]["resolved_saved_reference_counts"],
                             {"flag": 2, "variable": 1, "trainer_defeat": 1})
            self.assertTrue(any(x["kind"] == "c_special_or_non_array_state"
                                for x in output["donors"]["emerald"]["unknowns"]))
            self.assertTrue(any(x["kind"] == "unresolved_numeric_script"
                                for x in output["donors"]["platinum"]["unknowns"]))
            self.assertFalse(output["donors"]["platinum"]["reference_census_complete"])
            self.assertTrue(output["donors"]["emerald"]["git_dirty"])
            shared = output["donors"]["emerald"]["scoped_references"]
            self.assertTrue(any("data/scripts/shared.inc:7" in v["writes"]
                                for v in shared if v["category"] == "trainer_defeat"))
            self.assertTrue(any(v["id"] == "0x0930" for v in shared))
            self.assertTrue(any(v["id"] == "0x02DA" for v in
                                output["donors"]["platinum"]["scoped_references"]))
            self.assertTrue(any(v["id"] == "0x0041" and
                                "res/field/scripts/scripts_common.s:4" in v["writes"] for v in
                                output["donors"]["platinum"]["scoped_references"]))
            flower_flag = next(v for v in shared if v["id"] == "0x0930")
            self.assertEqual(flower_flag["reads"], [])
            one_flag = next(v for v in shared if v["id"] == "0x0040")
            self.assertIn("data/maps/Test/scripts.inc:4", one_flag["reads"])
            self.assertIn("data/maps/Test/scripts.inc:2", one_flag["writes"])
            one_var = next(v for v in shared if v["id"] == "0x4011")
            self.assertIn("data/maps/Test/scripts.inc:5", one_var["reads"])
            self.assertIn("data/maps/Test/scripts.inc:3", one_var["writes"])
            platinum_var = next(v for v in output["donors"]["platinum"]["scoped_references"]
                                if v["id"] == "0x4020")
            self.assertIn("res/field/scripts/scripts_test.s:4", platinum_var["reads"])
            self.assertIn("res/field/scripts/scripts_test.s:3", platinum_var["writes"])
            self.assertFalse(any("Common_CallNurse" in u["detail"] or
                                 "Common_GiveItemQuantity" in u["detail"] or
                                 "CallCommonScript 0x7D2" in u["detail"]
                                 for u in output["donors"]["platinum"]["unknowns"]))
            self.assertIn("data/scripts/shared.inc",
                          output["donors"]["emerald"]["source_sha256"])
            self.assertIn("asm/macros/scrcmd.inc",
                          output["donors"]["platinum"]["source_sha256"])
            manager = platinum / "src/script_manager.c"
            manager.write_text(manager.read_text().replace(
                "return scriptID - SCRIPT_ID_OFFSET_HIDDEN_ITEMS + HIDDEN_ITEM_FLAGS_START;",
                "return 0;"))
            with self.assertRaisesRegex(ValueError, "unverified hidden-item"):
                census.report(emerald, platinum, scope)

    def test_missing_scope_input_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "generated").mkdir()
            (root / "generated/vars_flags.txt").write_text("FLAG_UNUSED_0x0000\n")
            (root / "generated/trainers.txt").write_text("TRAINER_NONE\n")
            with self.assertRaisesRegex(ValueError, "scope input missing"):
                census.census(root, "platinum", {
                    "maps": ["missing"], "badge_evidence": "missing", "selection": "test"})

    @unittest.skipUnless(os.environ.get("CAMPAIGN_EMERALD") and
                         os.environ.get("CAMPAIGN_PLATINUM"),
                         "owner-local donor paths not explicitly supplied")
    def test_optional_owner_local_anchors(self):
        report = census.report(Path(os.environ["CAMPAIGN_EMERALD"]),
                               Path(os.environ["CAMPAIGN_PLATINUM"]))
        e, p = report["donors"]["emerald"], report["donors"]["platinum"]
        def entry(donor, name):
            return next(v for v in donor["scoped_references"] if name in v["names"])
        self.assertEqual(entry(e, "FLAG_DAILY_FLOWER_SHOP_RECEIVED_BERRY")["id"], "0x0930")
        self.assertIn("data/maps/Route104_PrettyPetalFlowerShop/scripts.inc:82",
                      entry(e, "FLAG_DAILY_FLOWER_SHOP_RECEIVED_BERRY")["reads"])
        self.assertNotIn("data/maps/Route104_PrettyPetalFlowerShop/scripts.inc:82",
                         entry(e, "FLAG_DAILY_FLOWER_SHOP_RECEIVED_BERRY")["writes"])
        self.assertIn("data/maps/Route104_PrettyPetalFlowerShop/scripts.inc:88",
                      entry(e, "FLAG_DAILY_FLOWER_SHOP_RECEIVED_BERRY")["writes"])
        self.assertIn("data/scripts/set_gym_trainers.inc:14",
                      entry(e, "TRAINER_JOSH")["writes"])
        self.assertIn("res/field/events/events_oreburgh_city.json:20",
                      entry(p, "FLAG_OBTAINED_HIDDEN_OREBURGH_CITY_PEARL")["reads"])
        self.assertEqual(entry(p, "FLAG_OBTAINED_HIDDEN_OREBURGH_CITY_HEART_SCALE")["id"],
                         "0x03DB")
        self.assertIn("res/field/scripts/scripts_common.s:191",
                      entry(p, "FLAG_POKECENTER_IDENTIFIED_POKERUS")["writes"])
        self.assertIn("src/script_manager.c", p["source_sha256"])
        self.assertIn("data/event_scripts.s", e["source_sha256"])
        lifetime_source = Path(os.environ["CAMPAIGN_EMERALD"]) / "src/event_data.c"
        self.assertEqual(e["source_sha256"]["src/event_data.c"],
                         hashlib.sha256(lifetime_source.read_bytes()).hexdigest())
        self.assertFalse(any("Common_CallPokecenterNurse" in u["detail"] or
                             "Common_GiveItemQuantity" in u["detail"]
                             for u in p["unknowns"]))
        self.assertFalse(p["reference_census_complete"])


if __name__ == "__main__":
    unittest.main()