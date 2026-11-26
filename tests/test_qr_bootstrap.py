import tempfile
import unittest
from pathlib import Path
from mautrix_max.qr_bootstrap import commit_session


class CommitSessionTests(unittest.TestCase):
    def test_publishes_only_completed_session_and_marker(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); stage=root/'staging';stage.mkdir();(stage/'session.db').write_bytes(b'fake')
            final=root/'sessions'/'owner'; marker=root/'pending'/'owner'
            commit_session(stage,final,marker)
            self.assertEqual((final/'session.db').read_bytes(),b'fake')
            self.assertTrue(marker.is_file())
            self.assertFalse(stage.exists())
            self.assertNotIn('fake',marker.read_text())
    def test_does_not_overwrite_existing_session(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); stage=root/'staging';stage.mkdir();(stage/'session.db').write_bytes(b'new')
            final=root/'sessions'/'owner';final.mkdir(parents=True);(final/'session.db').write_bytes(b'existing')
            with self.assertRaises(FileExistsError):commit_session(stage,final,root/'pending'/'owner')
            self.assertEqual((final/'session.db').read_bytes(),b'existing')
            self.assertTrue(stage.exists())
    def test_requires_session_file(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); stage=root/'staging';stage.mkdir()
            with self.assertRaises(ValueError):commit_session(stage,root/'sessions'/'owner',root/'pending'/'owner')
            self.assertFalse((root/'pending'/'owner').exists())

if __name__ == '__main__':unittest.main()
