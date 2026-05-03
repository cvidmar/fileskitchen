"""
workflow_raw.py — Delete ARW files that have no corresponding JPG.

Usage:
    python workflow_raw.py /path/to/photos          # dry run (default)
    python workflow_raw.py /path/to/photos --run    # actually delete
"""

import sys
from pathlib import Path
from fileset import tree

# ── Config ────────────────────────────────────────────────────────────────────

folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
dry    = "--run" not in sys.argv

# ── Pipeline ──────────────────────────────────────────────────────────────────

jpgs = tree(folder, "JPG", dry=dry)
raws = tree(folder, "ARW", dry=dry)

orphans = raws.not_paired_in(jpgs, self_root=folder, other_root=folder)

print(f"\n📷  JPGs found   : {jpgs.count()}")
print(f"📷  RAWs found   : {raws.count()}")
print(f"🗑️   Orphan RAWs  : {orphans.count()}")
print(f"{'[DRY RUN — pass --run to delete]' if dry else '[LIVE RUN]'}\n")

if orphans.count() == 0:
    print("Nothing to do.")
else:
    orphans.delete()
