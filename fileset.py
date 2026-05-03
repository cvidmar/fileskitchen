"""
fileset.py — A fluent file pipeline library.
Core primitive: FileSet — an immutable, composable snapshot of paths.
"""

from __future__ import annotations
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence


# ── Colour helpers (no deps) ──────────────────────────────────────────────────

_R = "\033[31m"  # red
_G = "\033[32m"  # green
_Y = "\033[33m"  # yellow
_B = "\033[34m"  # blue
_D = "\033[2m"   # dim
_X = "\033[0m"   # reset


def _fmt(symbol: str, color: str, label: str, path: str) -> str:
    return f"  {color}{symbol}{_X} {_D}{label}{_X}  {path}"


# ── Result type ───────────────────────────────────────────────────────────────

class Result:
    def __init__(self, path: Path, ok: bool, detail: str = ""):
        self.path   = path
        self.ok     = ok
        self.detail = detail

    def __repr__(self):
        mark = f"{_G}✓{_X}" if self.ok else f"{_R}✗{_X}"
        return f"{mark} {self.path}" + (f"  ({self.detail})" if self.detail else "")


# ── Core FileSet ──────────────────────────────────────────────────────────────

class FileSet:
    """
    Immutable, chainable collection of Paths.

    Construction:
        files("src/**/*.py")          — glob
        files(["a.txt", "b.txt"])     — explicit list
        FileSet.from_dir("src", "py") — all files with extension in a dir tree

    Filtering:
        .where(predicate)             — keep matching files
        .exclude(predicate)           — drop matching files
        .with_ext(ext)                — keep by extension
        .not_paired_in(other, ...)    — set-difference by stem key

    Introspection:
        .count()                      — number of files
        .preview(n)                   — print first n paths
        .stems()                      — return list of stems (no ext)
        .paths()                      — return list of Paths

    Actions:
        .each(fn)                     — call fn(path) for every file
        .delete()                     — rm every file
        .move_to(dest_root, new_ext)  — mirror tree with optional ext swap
        .run_command(template)        — command per file
        .remove_empty_dirs(root)      — prune empty dirs under root

    All actions respect .dry_run() mode, which is enabled by default.
    """

    def __init__(
        self,
        paths: Iterable[Path],
        *,
        dry: bool = True,
        _root: Optional[Path] = None,  # used internally for relative display
    ):
        self._paths: list[Path] = _unique_paths(paths)
        self._dry   = dry
        self._root  = Path(_root).resolve() if _root else None

    # ── Construction helpers ──────────────────────────────────────────────────

    @classmethod
    def from_glob(cls, pattern: str, dry: bool = True) -> "FileSet":
        import glob as _glob
        paths = sorted(
            (Path(p) for p in _glob.glob(pattern, recursive=True) if Path(p).is_file()),
            key=lambda p: str(p).lower(),
        )
        return cls(paths, dry=dry)

    @classmethod
    def from_dir(cls, root: str, ext: str, dry: bool = True) -> "FileSet":
        root_path = Path(root).resolve()
        ext_norm  = ext.lstrip(".").lower()
        paths = sorted(
            (
                p for p in root_path.rglob("*")
                if p.is_file() and p.suffix.lstrip(".").lower() == ext_norm
            ),
            key=lambda p: str(p).lower(),
        )
        return cls(paths, dry=dry, _root=root_path)

    # ── Config ────────────────────────────────────────────────────────────────

    def dry_run(self, enabled: bool = True) -> "FileSet":
        """Return a new FileSet with dry-run mode changed."""
        return FileSet(self._paths, dry=enabled, _root=self._root)

    # ── Filtering ─────────────────────────────────────────────────────────────

    def where(self, predicate: Callable[[Path], bool]) -> "FileSet":
        return FileSet([p for p in self._paths if predicate(p)], dry=self._dry, _root=self._root)

    def exclude(self, predicate: Callable[[Path], bool]) -> "FileSet":
        return self.where(lambda p: not predicate(p))

    def with_ext(self, *exts: str) -> "FileSet":
        norm = {e.lstrip(".").lower() for e in exts}
        return self.where(lambda p: p.suffix.lstrip(".").lower() in norm)

    def not_paired_in(
        self,
        other: "FileSet",
        *,
        self_root:  Optional[Path] = None,
        other_root: Optional[Path] = None,
    ) -> "FileSet":
        """
        Return files in self whose stem-key (relative path without extension)
        does NOT appear in other.  Used for set-difference across two trees.

        self_root / other_root strip the leading directory so stems are
        comparable across different base paths.
        """
        sr = Path(self_root).resolve()  if self_root  else self._root
        or_ = Path(other_root).resolve() if other_root else other._root

        def _key(p: Path, root: Optional[Path]) -> str:
            rel = p.relative_to(root) if root else p
            return str(rel.with_suffix("")).lower()

        other_keys = {_key(p, or_) for p in other._paths}
        return self.where(lambda p: _key(p, sr) not in other_keys)

    def also_in(
        self,
        other: "FileSet",
        *,
        self_root:  Optional[Path] = None,
        other_root: Optional[Path] = None,
    ) -> "FileSet":
        """Opposite of not_paired_in — keep only files that DO have a counterpart."""
        sr  = Path(self_root).resolve()  if self_root  else self._root
        or_ = Path(other_root).resolve() if other_root else other._root

        def _key(p: Path, root: Optional[Path]) -> str:
            rel = p.relative_to(root) if root else p
            return str(rel.with_suffix("")).lower()

        other_keys = {_key(p, or_) for p in other._paths}
        return self.where(lambda p: _key(p, sr) in other_keys)

    # ── Introspection ─────────────────────────────────────────────────────────

    def count(self) -> int:
        return len(self._paths)

    def stems(self) -> list[str]:
        return [p.stem for p in self._paths]

    def paths(self) -> list[Path]:
        return list(self._paths)

    def preview(self, n: int = 20) -> "FileSet":
        shown = self._paths[:n]
        root  = self._root
        for p in shown:
            display = p.relative_to(root) if root and p.is_relative_to(root) else p
            print(f"  {_D}{display}{_X}")
        if len(self._paths) > n:
            print(f"  {_D}… and {len(self._paths) - n} more{_X}")
        return self

    def __repr__(self) -> str:
        return f"FileSet({self.count()} files{'  [DRY RUN]' if self._dry else ''})"

    def __len__(self) -> int:
        return self.count()

    def __iter__(self):
        return iter(self._paths)

    # ── Actions ───────────────────────────────────────────────────────────────

    def each(self, fn: Callable[[Path], None]) -> list[Result]:
        results = []
        for p in self._paths:
            if self._dry:
                print(_fmt("→", _B, "would process", str(p)))
                results.append(Result(p, True, "dry"))
            else:
                try:
                    fn(p)
                    results.append(Result(p, True))
                except Exception as e:
                    print(_fmt("✗", _R, "error", f"{p}  ({e})"))
                    results.append(Result(p, False, str(e)))
        return results

    def delete(self) -> list[Result]:
        """Delete every file in the set."""
        results = []
        for p in self._paths:
            if self._dry:
                print(_fmt("✗", _R, "would delete", str(p)))
                results.append(Result(p, True, "dry"))
            else:
                try:
                    p.unlink()
                    print(_fmt("✗", _R, "deleted", str(p)))
                    results.append(Result(p, True))
                except Exception as e:
                    print(_fmt("!", _Y, "error", f"{p}  ({e})"))
                    results.append(Result(p, False, str(e)))
        return results

    def move_to(
        self,
        dest_root: str | Path,
        *,
        new_ext:    Optional[str]  = None,
        src_root:   Optional[str | Path] = None,
    ) -> list[Result]:
        """
        Mirror the tree structure under dest_root.
        Optionally change file extensions (e.g. .flac → .mp3).
        Returns one Result per attempted move.
        """
        dest   = Path(dest_root).resolve()
        src_r  = Path(src_root).resolve() if src_root else self._root
        results = []

        for p in self._paths:
            try:
                rel  = p.relative_to(src_r) if src_r else Path(p.name)
                dest_path = dest / rel
                if new_ext:
                    dest_path = dest_path.with_suffix("." + new_ext.lstrip("."))

                if self._dry:
                    print(_fmt("→", _B, "would move", f"{p}  →  {dest_path}"))
                    results.append(Result(p, True, f"dry -> {dest_path}"))
                else:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), dest_path)
                    print(_fmt("→", _G, "moved", str(dest_path)))
                    results.append(Result(p, True, f"-> {dest_path}"))
            except Exception as e:
                print(_fmt("!", _Y, "error", f"{p}  ({e})"))
                results.append(Result(p, False, str(e)))

        return results

    def run_command(
        self,
        template: str | Sequence[str],
        *,
        src_root: Optional[str | Path] = None,
        dest_root: Optional[str | Path] = None,
        new_ext:   Optional[str]  = None,
    ) -> list[Result]:
        """
        Run a command for each file. String templates are parsed with shlex
        and executed without a shell.
        Template variables:
            {src}      — absolute source path
            {dest}     — mirrored path under dest_root (with optional new_ext)
            {stem}     — filename without extension
            {name}     — filename with extension
            {parent}   — parent directory
        Destination directories are created automatically.
        """
        src_r  = Path(src_root).resolve()  if src_root  else self._root
        dest_r = Path(dest_root).resolve() if dest_root else None
        results = []

        for p in self._paths:
            try:
                rel  = p.relative_to(src_r) if src_r else Path(p.name)
                dest_path = dest_r / rel if dest_r else p
                if new_ext and dest_r:
                    dest_path = dest_path.with_suffix("." + new_ext.lstrip("."))

                argv = _format_command(
                    template,
                    src    = str(p),
                    dest   = str(dest_path),
                    stem   = p.stem,
                    name   = p.name,
                    parent = str(p.parent),
                )
                cmd = shlex.join(argv)

                if self._dry:
                    print(_fmt("▶", _B, "would run", cmd))
                    results.append(Result(p, True, "dry"))
                else:
                    if dest_r:
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                    print(_fmt("▶", _G, "running", cmd))
                    proc = subprocess.run(argv)
                    ok   = proc.returncode == 0
                    results.append(Result(p, ok, f"exit {proc.returncode}"))
            except Exception as e:
                print(_fmt("!", _Y, "error", f"{p}  ({e})"))
                results.append(Result(p, False, str(e)))
        return results

    def remove_empty_dirs(self, root: str | Path) -> int:
        """
        Walk root bottom-up and remove empty directories.
        Returns number of dirs removed.
        """
        root_path = Path(root).resolve()
        removed   = 0
        # os.walk bottom-up guarantees we process deepest dirs first
        for dirpath, dirs, files in os.walk(root_path, topdown=False):
            d = Path(dirpath)
            if d == root_path:
                continue
            try:
                entries = list(d.iterdir())
            except Exception:
                continue
            if not entries:
                if self._dry:
                    print(_fmt("✗", _Y, "would rmdir", str(d)))
                else:
                    d.rmdir()
                    print(_fmt("✗", _Y, "rmdir", str(d)))
                removed += 1
        return removed


# ── Convenience entry point ───────────────────────────────────────────────────

def files(source: str | list, *, dry: bool = True) -> FileSet:
    """
    Main entry point.

        files("photos/**/*.jpg")         — glob pattern
        files(["a.txt", "b.txt"])        — explicit list
    """
    if isinstance(source, list):
        return FileSet(source, dry=dry)
    return FileSet.from_glob(source, dry=dry)


def tree(root: str, ext: str, *, dry: bool = True) -> FileSet:
    """
    Recursively collect all files with a given extension under root.

        tree("/music/flac", "flac")
        tree("/photos/raw", "ARW")
    """
    return FileSet.from_dir(root, ext, dry=dry)


def _unique_paths(paths: Iterable[Path]) -> list[Path]:
    seen = set()
    unique = []
    for path in paths:
        resolved = Path(path).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _format_command(template: str | Sequence[str], **values: str) -> list[str]:
    parts = shlex.split(template) if isinstance(template, str) else [str(p) for p in template]
    if not parts:
        raise ValueError("empty command template")
    return [part.format(**values) for part in parts]
