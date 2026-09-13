"""Bob UserPromptSubmit hook: if the prompt mentions an existing .str file, decode it (cached) and print its summary.

stdin : {"event": "UserPromptSubmit", "session_id": "...", "prompt": "..."}
stdout: injected into the model context. Never blocks the prompt (always exit 0).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import CLI_HINT, find_str_files, load_config, log, read_text, rel_to, setup_utf8_stdio, to_posix  # noqa: E402

STR_TOKEN_RE = re.compile(r"""@?((?:[A-Za-z]:)?[^\s"'<>|*?`]+\.str)(?![\w.])""", re.I)


def candidates(prompt: str, root: Path, cfg: dict) -> list[Path]:
    found: list[Path] = []
    seen: set = set()

    def add(p: Path):
        try:
            rp = p.resolve()
        except OSError:
            return
        if rp.is_file() and rp.suffix.lower() == ".str" and str(rp).lower() not in seen:
            seen.add(str(rp).lower())
            found.append(rp)

    for m in STR_TOKEN_RE.finditer(prompt):
        tok = m.group(1).strip().lstrip("@").strip()
        for cand in (tok, tok.lstrip("/\\")):
            p = Path(cand)
            add(p if p.is_absolute() else root / cand)
    if ".str" in prompt.lower():
        low = prompt.lower()
        for f in find_str_files(root, cfg):
            if f.name.lower() in low:
                add(f)
    return found


def main() -> int:
    setup_utf8_stdio()
    raw_text = ""
    try:
        raw_text = sys.stdin.buffer.read().decode("utf-8", "replace")
        data = json.loads(raw_text or "{}")
        prompt = str(data.get("prompt") or "")
    except Exception as e:
        # malformed JSON: fall back to scanning the raw text (never block the prompt)
        log("hook_prompt: stdin is not valid JSON (%s); scanning raw text" % e, "hooks.log")
        prompt = raw_text
    if ".str" not in prompt.lower():
        return 0
    cfg = load_config()
    root = Path.cwd()
    files = candidates(prompt, root, cfg)[: int(cfg.get("max_prompt_files", 3))]
    if not files:
        return 0
    from decode import DecodeError, decode_stream
    max_lines = int(cfg.get("summary_max_lines", 300))
    for f in files:
        try:
            r = decode_stream(f, cfg, root=root)
            text = read_text(r["summary_path"])
            lines = text.splitlines()
            if len(lines) > max_lines:
                text = "\n".join(lines[:max_lines]) + "\n... (truncated; full text: %s)\n" % to_posix(r["summary_path"])
            print('<spss-stream-context file="%s" decoded_dir="%s" cached="%s">' % (
                rel_to(f, root), rel_to(r["dir"], root), "true" if r["cached"] else "false"))
            print(text.rstrip("\n"))
            print("</spss-stream-context>")
            log("hook_prompt: injected %s (cached=%s)" % (f, r["cached"]), "hooks.log")
        except DecodeError as e:
            print("[strcodec] %s could not be decoded automatically: %s" % (rel_to(f, root), str(e).splitlines()[0]))
            print("[strcodec] The .str file is binary; do not read it with read_file. Use skill spss-str-decode "
                  "(%s decode \"%s\") and check .bob/strcodec/logs/." % (CLI_HINT, to_posix(f)))
            log("hook_prompt: decode failed for %s: %s" % (f, e), "hooks.log")
        except Exception as e:  # never block the prompt
            print("[strcodec] unexpected error while decoding %s: %s" % (rel_to(f, root), e))
            log("hook_prompt: unexpected error for %s: %r" % (f, e), "hooks.log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
