"""Fast contract tests for the batch importer, not a regional playthrough."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from emerald_region_battles import brace_body
from emerald_region_data import split_chunks, terrain_word
from emerald_region_graphics import map_model, texture_pages
from emerald_region_scripts import Bank, Scripts, Unsupported
from hgss_land import Land, flat_bdhc
from prepare_hoenn_region import connection_cells, event_size, ranges


def scripts(blocks, names=None):
    result = object.__new__(Scripts)
    result.blocks = blocks
    result.names = names or {}
    result.battles = None
    result.locations = {}
    return result


class HoennRegionTests(unittest.TestCase):
    def test_larger_maps_split_without_coordinate_truncation(self):
        self.assertEqual(len(split_chunks(40, 140)), 10)
        self.assertEqual(split_chunks(33, 33), [(0, 0), (1, 0), (0, 1), (1, 1)])
        with self.assertRaises(ValueError):
            split_chunks(0, 10)

    def test_unknown_terrain_is_not_silently_walkable(self):
        self.assertEqual(terrain_word(3 << 12, 0), (0, None))
        self.assertEqual(terrain_word((3 << 12) | (1 << 10), 0), (0x8000, None))
        self.assertEqual(terrain_word(3 << 12, 0x53), (0x8000, 0x53))
        self.assertEqual(terrain_word(3 << 12, 2), (2, None))

    def test_physical_mixed_4_and_8_bit_texture_pixels(self):
        tiles = [tuple((x + y) % 11 for y in range(16) for x in range(16)),
                 tuple((x + y * 16) % 71 for y in range(16) for x in range(16))]
        encoded, mapping, pages, stats = texture_pages(tiles)
        section = struct.unpack_from("<I", encoded, 16)[0]
        texture = encoded[section:]
        image_offset = struct.unpack_from("<I", texture, 20)[0]
        palette_offset = struct.unpack_from("<I", texture, 56)[0]
        self.assertEqual({p["param"] >> 26 & 7 for p in pages}, {3, 4})
        for tile in tiles:
            page, x, y = mapping[tile]
            p = pages[page]
            colors = struct.unpack_from(f"<{p['palette_colors']}H", texture,
                                        palette_offset + p["palette_offset"])
            output = []
            for dy in range(16):
                for dx in range(16):
                    index = (y + dy) * p["width"] + x + dx
                    origin = image_offset + (p["param"] & 0xFFFF) * 8
                    if p["param"] >> 26 & 7 == 3:
                        byte = texture[origin + index // 2]
                        index = byte >> (index % 2 * 4) & 15
                    else:
                        index = texture[origin + index]
                    output.append(colors[index])
            self.assertEqual(tuple(output), tile)
        self.assertLessEqual(stats["texture_bytes"], 102400)

    def test_model_fits_existing_slot_and_land_codec(self):
        tiles = [tuple([color] * 256) for color in range(40)]
        _, mapping, pages, _ = texture_pages(tiles)
        model = map_model([tiles[i % len(tiles)] for i in range(1024)], mapping, pages)
        self.assertLessEqual(len(model), 0xE000)
        land = Land(0x1234, b"", bytes(2048), b"", model,
                    flat_bdhc(-256, -256, 256, 256))
        self.assertEqual(Land.decode(land.encode()), land)

    def test_palettes_are_not_lossily_quantized(self):
        with self.assertRaises(ValueError):
            texture_pages([tuple([32768] * 256)])
        tiles = [tuple([i] * 256) for i in range(80)]
        first = texture_pages(tiles)
        second = texture_pages(tiles)
        self.assertEqual(first, second)

    def test_native_event_bound_includes_all_record_types(self):
        event = dict(objects=[{}] * 46, bgs=[{}] * 18, warps=[{}] * 5, coords=[{}] * 34)
        self.assertEqual(event_size(event), 2452)
        self.assertGreaterEqual(event_size(event), 0x800)

    def test_connection_offset_and_landing_inset(self):
        layout = dict(width=8, height=8, blocks=(3 << 12,) * 64,
                      tiles={0: ((0,) * 256, 0)})
        cells = connection_cells(layout, layout, dict(direction="up", offset=3))
        self.assertEqual(cells[0], (3, (3, 0), (0, 6)))
        self.assertEqual(cells[-1], (7, (7, 0), (4, 6)))
        self.assertEqual(connection_cells(layout, layout, dict(direction="dive", offset=0)), [])
        self.assertEqual(ranges([1, 2, 3, 8, 10, 11]), [[1, 3], [8, 8], [10, 11]])

    def test_unsupported_after_message_blocks_entire_interaction(self):
        source = scripts({"NPC": ["msgbox Text, MSGBOX_NPC", "special StoryMutation", "end"],
                          "Text": ['.string "Hello.$"']})
        bank = Bank(source, 831)
        bank.interaction("NPC")
        self.assertEqual(bank.coverage[0]["status"], "blocked-before-execution")
        self.assertNotIn("Hello.", bank.gmm().decode())
        self.assertNotIn("StoryMutation", bank.assembly())

    def test_scroll_and_player_name_are_preserved(self):
        source = scripts({"Text": [r'.string "Hi {PLAYER}!\n"', r'.string "Two\lThree\pNext.$"']})
        self.assertEqual(source.text("Text"),
                         r"Hi {STRVAR_1 3, 0, 0}!\nTwo\fThree\rNext.")

    def test_temp_flag_does_not_leak_into_persistent_namespace(self):
        source = scripts({"NPC": ["goto_if_set FLAG_TEMP, Done", "end"],
                          "Done": ["end"]}, {"FLAG_TEMP": 1})
        with self.assertRaises(Unsupported):
            source.closure("NPC")

    def test_cycle_through_jump_and_call_is_rejected(self):
        source = scripts({"A": ["goto B"], "B": ["call A", "return"]})
        with self.assertRaises(Unsupported):
            source.closure("A")

    def test_initializer_braces_inside_names_are_not_syntax(self):
        self.assertEqual(brace_body('{.name = _("{PLAYER}"), .party = {1, 2}} tail', 0),
                         '.name = _("{PLAYER}"), .party = {1, 2}')

    def test_pickup_receipt_has_checked_delivery_and_synchronous_rollback(self):
        source = scripts({"Item": ["finditem ITEM_POTION", "end"]})
        class Items:
            def item(self, name):
                if name != "ITEM_POTION":
                    raise ValueError("unknown item")
                return name
        source.battles = Items()
        bank = Bank(source, 831)
        bank.interaction("Item", object_flag=0x84)
        code = bank.assembly()
        self.assertEqual(bank.coverage[0]["status"], "converted")
        self.assertLess(code.index("GiveItem ITEM_POTION"), code.index("CampaignSetFlag"))
        self.assertIn("TakeItem ITEM_POTION, 1, 0x800C", code)
        self.assertIn("Compare 0x800B, 1", code)
        self.assertIn("Compare 0x800C, 1", code)

    def test_pickup_without_receipt_flag_is_not_repeatable_free_item(self):
        source = scripts({"Item": ["finditem ITEM_POTION", "end"]})
        bank = Bank(source, 831)
        bank.interaction("Item")
        self.assertEqual(bank.coverage[0]["status"], "blocked-before-execution")
        self.assertNotIn("GiveItem", bank.assembly())


if __name__ == "__main__":
    unittest.main()
