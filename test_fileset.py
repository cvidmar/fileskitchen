import contextlib
import io
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

from fileset import files, tree


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


class FileSetTests(unittest.TestCase):
    def test_default_dry_run_prevents_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "delete me.txt"
            path.write_text("content")

            results = quiet(files([path]).delete)

            self.assertTrue(path.exists())
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].ok)
            self.assertEqual(results[0].detail, "dry")

    def test_dry_run_returns_new_fileset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "live.txt"
            path.write_text("content")

            original = files([path])
            live = original.dry_run(False)

            self.assertIn("[DRY RUN]", repr(original))
            self.assertNotIn("[DRY RUN]", repr(live))

            quiet(original.delete)
            self.assertTrue(path.exists())

            quiet(live.delete)
            self.assertFalse(path.exists())

    def test_tree_uses_resolved_relative_root_for_actions(self):
        old_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                Path("src").mkdir()
                Path("src/a.txt").write_text("content")

                results = quiet(tree("src", "txt").move_to, "dest")

                self.assertEqual(len(results), 1)
                self.assertTrue(results[0].ok)
                self.assertIn(str((Path(tmp) / "dest" / "a.txt").resolve()), results[0].detail)
            finally:
                os.chdir(old_cwd)

    def test_tree_sorts_dedupes_and_matches_mixed_case_extensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b.TxT").write_text("b")
            (root / "a.txt").write_text("a")
            (root / "c.md").write_text("c")

            names = [p.name for p in tree(root, "txt").paths()]

            self.assertEqual(names, ["a.txt", "b.TxT"])

    def test_not_paired_uses_relative_case_insensitive_stems(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flac_root = root / "flac"
            mp3_root = root / "mp3"
            (flac_root / "Artist").mkdir(parents=True)
            (flac_root / "Other").mkdir(parents=True)
            (mp3_root / "artist").mkdir(parents=True)

            (flac_root / "Artist" / "Song.FLAC").write_text("flac")
            (flac_root / "Other" / "Missing.FlAc").write_text("flac")
            (mp3_root / "artist" / "song.mp3").write_text("mp3")

            orphans = tree(flac_root, "flac").not_paired_in(
                tree(mp3_root, "mp3"),
                self_root=flac_root,
                other_root=mp3_root,
            )

            self.assertEqual([p.name for p in orphans.paths()], ["Missing.FlAc"])

    def test_run_command_string_template_uses_argv_not_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src_root = root / "flac"
            dest_root = root / "mp3"
            src_root.mkdir()
            src = src_root / "song name; touch injected.flac"
            src.write_text("audio")

            template = (
                f"{shlex.quote(sys.executable)} -c "
                '"import pathlib, sys; pathlib.Path(sys.argv[2]).write_text(sys.argv[1])" '
                "{src} {dest}"
            )

            results = quiet(
                tree(src_root, "flac").dry_run(False).run_command,
                template,
                src_root=src_root,
                dest_root=dest_root,
                new_ext="txt",
            )

            dest = dest_root / "song name; touch injected.txt"
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].ok)
            self.assertEqual(dest.read_text(), str(src.resolve()))

    def test_move_to_returns_results_and_moves_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src.txt"
            dest_root = root / "dest"
            src.write_text("content")

            results = quiet(files([src]).dry_run(False).move_to, dest_root)

            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].ok)
            self.assertEqual(results[0].path, src.resolve())
            self.assertFalse(src.exists())
            self.assertEqual((dest_root / "src.txt").read_text(), "content")


if __name__ == "__main__":
    unittest.main()
