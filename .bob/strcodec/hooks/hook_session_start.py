"""Bob SessionStart hook: list .str files in the workspace (with cache state) and pre-decode them in the background.

stdout is injected into the model context as session information. Always exits 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import (CLI_HINT, TOOL_DIR, find_str_files, load_config, log, python_cmd_prefix, rel_to,  # noqa: E402
                    setup_utf8_stdio, spawn_detached, strcode_dir_for)


def main() -> int:
    setup_utf8_stdio()
    try:
        sys.stdin.buffer.read()  # consume payload; not needed
    except Exception:
        pass
    cfg = load_config()
    root = Path.cwd()
    try:
        files = find_str_files(root, cfg)
    except Exception as e:
        log("hook_session_start: scan failed: %s" % e, "hooks.log")
        return 0
    if not files:
        return 0
    from decode import is_cache_valid
    pending = 0
    print("<spss-stream-index>")
    print("SPSS Modeler stream files (.str, binary) in this workspace:")
    for f in files:
        d = strcode_dir_for(f)
        try:
            ok = is_cache_valid(f, d, cfg)
        except Exception:
            ok = False
        if not ok:
            pending += 1
        print("- %s (%d bytes) -> %s" % (rel_to(f, root), f.stat().st_size,
                                          ("decoded: %s/summary.md, stream.py" % rel_to(d, root)) if ok else "not decoded yet"))
    print("Rules: never read .str/.nod with read_file. To inspect a stream use skill `spss-str-decode` "
          "(%s decode \"<path>\" prints the summary; cached after the first run). "
          "To reproduce/modify a stream use skill `spss-str-rebuild`." % CLI_HINT)
    print("</spss-stream-index>")
    if pending and cfg.get("prewarm", True):
        try:
            # inherit this interpreter and its isolation flags (never switch to another Python)
            cmd = python_cmd_prefix() + [str(TOOL_DIR / "strcodec.py"), "prewarm", "--root", str(root),
                                         "--max", str(int(cfg.get("prewarm_max_files", 10)))]
            spawn_detached(cmd, root)
            log("hook_session_start: prewarm spawned for %d file(s)" % pending, "hooks.log")
        except Exception as e:
            log("hook_session_start: prewarm spawn failed: %s" % e, "hooks.log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
