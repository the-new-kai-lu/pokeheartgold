"""Execute native computed-variable accessors against bounded vanilla storage.

This closes the small sys_vars range question, not script dataflow or the
allocation decision. Invalid indices rejected only by GF_ASSERT are not
considered proven safe in a release ROM.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def extract(source, name):
    match = re.search(r"^(?:void|BOOL|u16|u32)\s+" + name + r"\(", source, re.M)
    if match is None:
        raise AssertionError(f"missing production function {name}")
    start = source.index("{", match.start())
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


class NativeVariableRangesTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("cc"), "host C compiler required")
    def test_native_ranges_preserve_candidate_slots(self):
        source = (ROOT / "src/sys_vars.c").read_text()
        arrays = "\n".join(
            re.search(r"static const u16 " + name + r"\[\] = \{.*?\};",
                      source, re.S).group()
            for name in ("_020FE4A4", "_020FE4A8")
        )
        functions = "\n".join(extract(source, name) for name in (
            "sub_02066B80", "sub_02066B9C", "sub_02066BC0",
            "sub_02066BE8", "sub_02066C00", "sub_02066C1C",
            "sub_02066C4C", "sub_02066C74",
        ))
        harness = r"""
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "constants/vars.h"
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef int BOOL;
#define GF_ASSERT assert
#define NELEMS(a) (sizeof(a) / sizeof((a)[0]))
typedef struct { u16 vars[NUM_VARS]; } SaveVarsFlags;
static unsigned reads, writes;
static u16 last;
static BOOL SetScriptVar(SaveVarsFlags *s, u16 id, u16 value) {
    assert(id >= VAR_BASE && id <= VARS_END);
    writes++; last = id; s->vars[id - VAR_BASE] = value; return 1;
}
static u16 GetScriptVar(SaveVarsFlags *s, u16 id) {
    assert(id >= VAR_BASE && id <= VARS_END);
    reads++; last = id; return s->vars[id - VAR_BASE];
}
"""
        main = r"""
int main(void) {
    SaveVarsFlags state;
    unsigned i;
    memset(&state, 0, sizeof(state));
    state.vars[0x416e - VAR_BASE] = 0x1234;
    state.vars[0x416f - VAR_BASE] = 0x5678;
    for (i = 0; i < NELEMS(_020FE4A4); i++) {
        sub_02066B9C(&state, i);
        assert(last == VAR_UNK_4043 + i);
        assert(sub_02066BC0(&state, i));
    }
    for (i = 0; i < NELEMS(_020FE4A8); i++) {
        sub_02066C1C(&state, i);
        assert(last == VAR_UNK_4036 + i);
        assert(sub_02066C74(&state, i));
        sub_02066C4C(&state, i);
        assert(!sub_02066C74(&state, i));
        sub_02066BE8(&state, i, 7);
        assert(last == VAR_ROAMER_RAIKOU_STATUS + i);
    }
    assert(reads == 10 && writes == 14);
    /* This accessor has a real runtime guard, not merely an assertion. */
    for (i = 4; i < 65536; i++)
        sub_02066BE8(&state, i, 9);
    sub_02066BE8(&state, UINT32_MAX, 9);
    assert(writes == 14);
    assert(state.vars[0x416e - VAR_BASE] == 0x1234);
    assert(state.vars[0x416f - VAR_BASE] == 0x5678);
    return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            cfile = Path(tmp) / "ranges.c"
            binary = Path(tmp) / "ranges"
            cfile.write_text(harness + arrays + functions + main)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-iquote", str(ROOT / "include"), str(cfile),
                            "-o", str(binary)], check=True)
            subprocess.run([str(binary)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()