#!/usr/bin/env python3
"""Three-point file-state recorder for the ESP four-group comparison.

Records, per file: existence, object identity (dev:ino via stat %d %i),
size, sha256, mode, uid, gid, atime, mtime, ctime. JSON output.

Recording-action side effects (documented, unavoidable): the sha256 read goes
through the FUSE proxy -> MediaProvider read path and reads the backing file;
under relatime the backing atime may advance. stat() itself does not change
data. mtime/ctime are not changed by reads. The "atime" field of the NEXT
snapshot therefore reflects this recorder, not the experiment alone; the
field "recorder_note" marks it.
"""
import json, subprocess, sys, time
from pathlib import Path

ADB = "adb"
SERIAL = "0.0.0.0:6528"
BASE = "/data/media/0/espafd_tree"


def sh(c, timeout=60):
    p = subprocess.run([ADB, "-s", SERIAL, "shell", c],
                       capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError("adb failed rc=%d: %s" % (p.returncode, p.stderr[:400]))
    return p.stdout.strip()


def snapshot(files, tag, outdir, note=""):
    rows = []
    for f in files:
        path = f"{BASE}/{f}"
        exists = sh(f'test -e "{path}" && echo 1 || echo 0') == "1"
        if not exists:
            rows.append(dict(tag=tag, file=f, exists=False, note="target absent"))
            continue
        st = sh(f'stat -c "%d %i %s %a %u %g %X %Y %Z" "{path}"')
        parts = st.split()
        dev, ino = parts[0], parts[1]
        digest = sh(f'sha256sum "{path}" | cut -d" " -f1')
        rows.append(dict(tag=tag, file=f, exists=True, dev=dev, ino=ino,
                         size=int(parts[2]), mode=parts[3], uid=parts[4],
                         gid=parts[5], atime=int(parts[6]), mtime=int(parts[7]),
                         ctime=int(parts[8]), sha256=digest,
                         recorder_note=("sha256 read via FUSE may advance atime "
                                        "(relatime); mtime/ctime unchanged by read")))
    out = Path(outdir) / f"file_state_{tag}.json"
    out.write_text(json.dumps(dict(tag=tag, ts_ns=time.time_ns(),
                                   recorder="host adb stat+sha256sum",
                                   recording_action_side_effects=note or
                                   "see per-row recorder_note",
                                   rows=rows), indent=1))
    print("wrote", out)
    return rows


if __name__ == "__main__":
    files = sys.argv[1].split(",")
    tag = sys.argv[2]
    outdir = sys.argv[3] if len(sys.argv) > 3 else "."
    note = sys.argv[4] if len(sys.argv) > 4 else ""
    snapshot(files, tag, outdir, note)
