# fileset — project context

## What this is

A fluent Python library for file pipeline operations, plus a thin REPL wrapper.
The core idea: file sets are the primitive, not text streams. You build pipelines
that select → filter → transform → act on collections of paths.

Born from the observation that one-off Python scripts solve file operation problems
well but don't compose or reuse. This library makes the framework stable so only
the workflow-specific bits (roots, patterns, command templates) change each time.

## Files

- `fileset.py`       — the library. Single file, stdlib only, ~250 lines.
- `workflow_raw.py`  — example: delete orphan RAW files when JPG has been culled.
- `workflow_music.py`— example: bidirectional FLAC↔MP3 mirror sync.
- `repl_demo.py`     — annotated REPL session transcript. Run with `python -i repl_demo.py`.

## Core API

```python
from fileset import tree, files

# Construction
tree(root, ext)           # all files with ext under root (recursive)
files("glob/**/*.jpg")    # glob pattern
files(["a.txt", "b.txt"]) # explicit list

# Filtering
.where(predicate)         # keep matching
.exclude(predicate)       # drop matching
.with_ext("jpg", "png")   # by extension
.not_paired_in(other, self_root=, other_root=)  # set-difference by stem key
.also_in(other, ...)      # set-intersection by stem key

# Introspection
.count()
.preview(n)
.stems()
.paths()

# Actions
.delete()
.move_to(dest, new_ext=)
.run_command(template, src_root=, dest_root=, new_ext=)
.each(fn)
.remove_empty_dirs(root)

# Dry run (default: on — actions preview)
.dry_run(True)            # stay in preview mode
.dry_run(False)           # opt in to live actions
```

The `not_paired_in` key is `relative_path_without_extension`, lowercased.
This normalises across different roots and extensions (e.g. FLAC vs MP3 trees).

## Design principles

- **Dry run by default, opt-in for live** — `--run` flag pattern in scripts.
- **No dependencies** — stdlib only. ffmpeg/convert/etc are called via `run_command`.
- **FileSet is immutable** — filtering and `.dry_run()` always return a new FileSet.
- **File actions return results** — list of `Result(path, ok, detail)` for inspection.
- **Colour output** — ANSI codes, ✓/✗/▶ symbols per action type.

## What's intentionally missing (good next steps)

- No parallelism — `run_command` is sequential. Natural next step: `par_each(fn, workers=4)`.
- No progress bar — fine for hundreds of files, noticeable at thousands.
- No config file — workflows are plain Python scripts. Could add a `~/.fileset/` plugin dir.
- No undo / transaction log — destructive actions are permanent.
- No content-based filtering — predicates work on metadata only (path, size, mtime).
  Adding `.where_content(fn)` that opens and inspects files would be powerful.
- The REPL is just `python -i` or `ipython -i`. A proper REPL with history persistence,
  tab-complete on FileSet methods, and `?` help could be a thin wrapper with `ptpython`.

## Conventions

- Extensions are normalised to lowercase for comparison, but preserved on disk.
- `self_root` / `other_root` in set operations strip leading paths before comparing stems.
  Always pass them when comparing across two trees.
- `run_command` template vars: `{src}`, `{dest}`, `{stem}`, `{name}`, `{parent}`.
  String templates are parsed with `shlex` and executed without a shell.
  Destination directories are `mkdir -p`'d automatically.
