"""
workflow_music.py — Mirror a FLAC tree as MP3, bidirectional sync.

Rules:
  1. FLAC exists, MP3 missing   → convert  (ffmpeg)
  2. MP3 exists, FLAC missing   → delete   (you sold the CD)
  3. Empty dirs in MP3 tree     → remove

Usage:
    python workflow_music.py                        # dry run with defaults
    python workflow_music.py --run                  # live run
    python workflow_music.py --flac /f --mp3 /m     # custom roots
"""

import sys
from pathlib import Path
from fileset import tree

# ── Config ────────────────────────────────────────────────────────────────────

args      = sys.argv[1:]
dry       = "--run" not in args
flac_root = Path(next((args[i+1] for i, a in enumerate(args) if a == "--flac"), "/music/flac"))
mp3_root  = Path(next((args[i+1] for i, a in enumerate(args) if a == "--mp3"),  "/music/mp3"))

FFMPEG = "ffmpeg -i {src} -q:a 2 -map_metadata 0 {dest}"

# ── Build sets ────────────────────────────────────────────────────────────────

flacs = tree(flac_root, "flac", dry=dry)
mp3s  = tree(mp3_root,  "mp3",  dry=dry)

to_convert = flacs.not_paired_in(mp3s,  self_root=flac_root, other_root=mp3_root)
to_purge   = mp3s.not_paired_in(flacs,  self_root=mp3_root,  other_root=flac_root)

# ── Report ────────────────────────────────────────────────────────────────────

print(f"\n🎵  FLACs        : {flacs.count()}")
print(f"🎵  MP3s         : {mp3s.count()}")
print(f"➕  To convert   : {to_convert.count()}")
print(f"🗑️   To purge     : {to_purge.count()}")
print(f"{'[DRY RUN — pass --run to execute]' if dry else '[LIVE RUN]'}\n")

# ── Step 1: Convert ───────────────────────────────────────────────────────────

if to_convert.count():
    print("── Step 1: Converting FLACs → MP3 ──────────────────")
    to_convert.run_command(
        FFMPEG,
        src_root  = flac_root,
        dest_root = mp3_root,
        new_ext   = "mp3",
    )
else:
    print("── Step 1: Nothing to convert ───────────────────────")

# ── Step 2: Purge ─────────────────────────────────────────────────────────────

if to_purge.count():
    print("\n── Step 2: Purging orphan MP3s ──────────────────────")
    to_purge.delete()
else:
    print("\n── Step 2: Nothing to purge ─────────────────────────")

# ── Step 3: Clean empty dirs ──────────────────────────────────────────────────

print("\n── Step 3: Removing empty directories ───────────────")
removed = to_purge.remove_empty_dirs(mp3_root)   # reuse any FileSet — method is on the class
print(f"   {removed} director{'y' if removed == 1 else 'ies'} removed")
