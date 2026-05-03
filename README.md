# Files Kitchen

![Files Kitchen logo](fileskitchen.png)

`Files Kitchen` is a small, stdlib-only Python library for file pipeline operations.
The core primitive is a `FileSet`: a composable snapshot of paths that you can
select, filter, compare, preview, and act on.

It is designed for the kind of file maintenance jobs that are easy to solve with
one-off Python scripts but awkward to reuse later:

```python
from fileset import tree

jpgs = tree("/photos/trip", "jpg")
raws = tree("/photos/trip", "arw")

orphans = raws.not_paired_in(jpgs, self_root="/photos/trip", other_root="/photos/trip")
orphans.preview()
orphans.delete()                # dry run by default
orphans.dry_run(False).delete() # live run
```

## Summary

- `tree(root, ext)` collects files with an extension under a directory tree.
- `files(pattern)` collects files from a glob pattern.
- `.where()`, `.exclude()`, and `.with_ext()` filter file sets.
- `.not_paired_in()` and `.also_in()` compare two trees by relative path without
  extension, case-insensitively.
- `.delete()`, `.move_to()`, `.run_command()`, `.each()`, and
  `.remove_empty_dirs()` perform actions.
- Actions are dry-run by default. Use `.dry_run(False)` or the workflow scripts'
  `--run` flag to opt into live changes.
- File actions return `Result(path, ok, detail)` objects for inspection.

There are no Python package dependencies. External tools such as `ffmpeg` can be
called through `run_command()`.

## Getting Started

Use Python 3.10 or newer.

Run the tests:

```bash
python3 -m unittest
```

Open the annotated REPL demo:

```bash
python3 -i repl_demo.py
```

Basic interactive use:

```python
from fileset import tree, files

photos = tree("/photos", "jpg")
photos.count()
photos.preview(10)

large = photos.where(lambda p: p.stat().st_size > 10 * 1024 * 1024)
large.preview()

jpegs = files("/photos/**/*.jpeg")
jpegs.dry_run(False).each(lambda p: print(f"{p} -> {p.with_suffix('.jpg')}"))
```

## Example: RAW Cleanup

`workflow_raw.py` deletes RAW files that no longer have a corresponding JPG.
This is useful after culling JPGs from a shoot and wanting to remove the matching
orphan RAW files.

Expected layout:

```text
/photos/trip/
  2024-08-15/
    IMG_0042.JPG
    IMG_0042.ARW
    IMG_0051.ARW
```

The pairing key is the relative path without extension, lowercased. In the
example above, `IMG_0042.JPG` pairs with `IMG_0042.ARW`; `IMG_0051.ARW` is an
orphan if there is no `IMG_0051.JPG`.

Preview what would be deleted:

```bash
python3 workflow_raw.py /photos/trip
```

Actually delete orphan RAW files:

```bash
python3 workflow_raw.py /photos/trip --run
```

The workflow is just:

```python
from fileset import tree

jpgs = tree(folder, "JPG", dry=dry)
raws = tree(folder, "ARW", dry=dry)

orphans = raws.not_paired_in(jpgs, self_root=folder, other_root=folder)
orphans.delete()
```

## Example: FLAC to MP3 Mirror

`workflow_music.py` keeps an MP3 mirror in sync with a FLAC library.

Rules:

- FLAC exists and MP3 is missing: convert with `ffmpeg`.
- MP3 exists and FLAC is missing: delete the orphan MP3.
- Empty directories in the MP3 tree: remove them.

Default roots are `/music/flac` and `/music/mp3`.

Preview the sync plan:

```bash
python3 workflow_music.py
```

Use custom roots:

```bash
python3 workflow_music.py --flac /path/to/flac --mp3 /path/to/mp3
```

Run the live sync:

```bash
python3 workflow_music.py --flac /path/to/flac --mp3 /path/to/mp3 --run
```

The core pipeline is:

```python
from fileset import tree

flacs = tree(flac_root, "flac", dry=dry)
mp3s = tree(mp3_root, "mp3", dry=dry)

to_convert = flacs.not_paired_in(mp3s, self_root=flac_root, other_root=mp3_root)
to_purge = mp3s.not_paired_in(flacs, self_root=mp3_root, other_root=flac_root)

to_convert.run_command(
    "ffmpeg -i {src} -q:a 2 -map_metadata 0 {dest}",
    src_root=flac_root,
    dest_root=mp3_root,
    new_ext="mp3",
)
to_purge.delete()
to_purge.remove_empty_dirs(mp3_root)
```

`run_command()` builds destination paths by mirroring the source tree under
`dest_root`. String templates are parsed with `shlex` and executed without a
shell, so filenames with spaces are handled correctly.
