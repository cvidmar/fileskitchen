"""
repl_demo.py — Annotated REPL session transcript.

Run with:  python -i repl_demo.py       (drops you into a live REPL after)
Or just:   ipython -i repl_demo.py      (nicer tab-completion + history)

The transcript below is intentionally not executed. It shows what a typical
interactive session looks like; in a real session, type or paste the lines one
at a time and inspect the output between steps.
"""

from fileset import tree, files   # that's the whole import


if False:
    # ═══════════════════════════════════════════════════════════════════════════════
    # SCENARIO A: Explore before committing (RAW workflow)
    # ═══════════════════════════════════════════════════════════════════════════════

    # --- Step 1: just look around ---

    jpgs = tree("/photos/trip", "JPG")
    raws = tree("/photos/trip", "ARW")

    jpgs          # → FileSet(312 files  [DRY RUN])
    raws          # → FileSet(312 files  [DRY RUN])  great, they match

    # --- Step 2: simulate a review session — you deleted some JPGs ---

    jpgs = tree("/photos/trip", "JPG")   # reload after your culling session
    raws = tree("/photos/trip", "ARW")

    jpgs          # → FileSet(187 files  [DRY RUN])
    raws          # → FileSet(312 files  [DRY RUN])  ← 125 orphans

    orphans = raws.not_paired_in(jpgs, self_root="/photos/trip", other_root="/photos/trip")
    orphans       # → FileSet(125 files  [DRY RUN])

    # --- Step 3: peek at what would be deleted ---

    orphans.preview(10)
    # /photos/trip/2024-08-15/IMG_0042.ARW
    # /photos/trip/2024-08-15/IMG_0051.ARW
    # ...

    # --- Step 4: dry run (default — no dry=True needed, it's the default) ---

    orphans.delete()
    # ✗ would delete  /photos/trip/2024-08-15/IMG_0042.ARW
    # ✗ would delete  /photos/trip/2024-08-15/IMG_0051.ARW
    # ...

    # --- Step 5: looks right, flip to live ---

    orphans.dry_run(False).delete()
    # ✗ deleted  /photos/trip/2024-08-15/IMG_0042.ARW
    # ...


    # ═══════════════════════════════════════════════════════════════════════════════
    # SCENARIO B: Music library — interactive diagnosis before running
    # ═══════════════════════════════════════════════════════════════════════════════

    FLAC = "/music/flac"
    MP3  = "/music/mp3"

    flacs = tree(FLAC, "flac")
    mp3s  = tree(MP3,  "mp3")

    flacs    # → FileSet(1847 files  [DRY RUN])
    mp3s     # → FileSet(1612 files  [DRY RUN])

    # --- What needs converting? ---

    to_convert = flacs.not_paired_in(mp3s, self_root=FLAC, other_root=MP3)
    to_convert   # → FileSet(241 files  [DRY RUN])

    to_convert.preview(5)
    # /music/flac/Portishead/Dummy/01-Mysterons.flac
    # /music/flac/Portishead/Dummy/02-Sour Times.flac
    # ...

    # --- What needs purging? ---

    to_purge = mp3s.not_paired_in(flacs, self_root=MP3, other_root=FLAC)
    to_purge     # → FileSet(6 files  [DRY RUN])

    to_purge.preview()
    # /music/mp3/Boards of Canada/Geogaddi/01-Ready Lets Go.mp3
    # ...

    # --- Sanity-check a specific artist before running ---

    boc = flacs.where(lambda p: "Boards of Canada" in str(p))
    boc          # → FileSet(47 files  [DRY RUN])

    boc_mp3 = mp3s.where(lambda p: "Boards of Canada" in str(p))
    boc_mp3      # → FileSet(41 files  [DRY RUN])   ← 6 missing, matches to_purge above

    # --- Run just the purge first (quicker to verify) ---

    to_purge.dry_run(False).delete()

    # --- Then run the full conversion (could take a while) ---

    to_convert.dry_run(False).run_command(
        "ffmpeg -i {src} -q:a 2 -map_metadata 0 {dest}",
        src_root  = FLAC,
        dest_root = MP3,
        new_ext   = "mp3",
    )

    # --- Clean up empty dirs ---

    to_purge.dry_run(False).remove_empty_dirs(MP3)
    # ✗ rmdir  /music/mp3/Boards of Canada/Geogaddi
    # ✗ rmdir  /music/mp3/Boards of Canada


    # ═══════════════════════════════════════════════════════════════════════════════
    # BONUS: ad-hoc one-liners that show the flexibility
    # ═══════════════════════════════════════════════════════════════════════════════

    # All FLACs larger than 50 MB
    tree(FLAC, "flac").where(lambda p: p.stat().st_size > 50 * 1024 * 1024)

    # All ARW files from a specific date (file-mtime based)
    import datetime
    cutoff = datetime.datetime(2024, 8, 1).timestamp()
    tree("/photos", "ARW").where(lambda p: p.stat().st_mtime > cutoff)

    # All FLACs that don't have a folder.jpg cover in the same dir
    tree(FLAC, "flac").where(lambda p: not (p.parent / "folder.jpg").exists())

    # Ad-hoc preview via a callback; opt into live mode because the callback only prints
    files("/photos/**/*.jpeg").dry_run(False).each(lambda p: print(f"{p} → {p.with_suffix('.jpg')}"))
