"""Integration self-test (needs SPSS Modeler clemb.exe, ~2 minutes).

  python .bob/strcodec/tests/selftest.py <file.str> [--retrain]

Copies the stream into a temp directory, decodes it, rebuilds it (transplant, and optionally retrain),
and verifies the rebuilt streams structurally. Exit 0 when every step passes.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "strcodec.py"


def run(args, cwd):
    print("$", " ".join(args))
    r = subprocess.run([sys.executable, str(TOOL)] + args, cwd=cwd, capture_output=True, encoding="utf-8", errors="replace")
    print(r.stdout[-2500:])
    if r.stderr.strip():
        print("stderr:", r.stderr[-1500:])
    return r.returncode


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    src = Path(sys.argv[1]).resolve()
    retrain = "--retrain" in sys.argv
    tmp = Path(tempfile.mkdtemp(prefix="strcodec_selftest_"))
    work = tmp / src.name
    shutil.copy2(src, work)
    ok = True
    ok &= run(["decode", str(work), "--quiet"], tmp) == 0
    ok &= run(["status"], tmp) == 0
    ok &= run(["rebuild", str(work), "--run"], tmp) == 0
    rebuilt = tmp / (src.stem + "_rebuilt.str")
    ok &= run(["verify", str(work), str(rebuilt)], tmp) == 0
    if retrain:
        retrained = tmp / (src.stem + "_retrained.str")
        ok &= run(["rebuild", str(work), "--run", "--retrain", "--out", str(retrained)], tmp) == 0
        ok &= run(["verify", str(work), str(retrained)], tmp) == 0
    print("SELFTEST", "PASS" if ok else "FAIL", "(artifacts in %s)" % tmp)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
