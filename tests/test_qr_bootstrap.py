import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mautrix_max.qr_bootstrap import commit_session, is_logged_out, session_in_use


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

    def test_reuses_directory_left_by_logout_and_keeps_device_profile(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); stage=root/'staging';stage.mkdir();(stage/'session.db').write_bytes(b'new')
            final=root/'sessions'/'owner';final.mkdir(parents=True);(final/'device-profile.json').write_text('{"profile": 1}')
            marker=root/'pending'/'owner'
            self.assertTrue(is_logged_out(final))
            commit_session(stage,final,marker)
            self.assertEqual((final/'session.db').read_bytes(),b'new')
            self.assertEqual((final/'device-profile.json').read_text(),'{"profile": 1}')
            self.assertTrue(marker.is_file())
            self.assertFalse(stage.exists())
    def test_refuses_directory_with_unknown_files(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); stage=root/'staging';stage.mkdir();(stage/'session.db').write_bytes(b'new')
            final=root/'sessions'/'owner';final.mkdir(parents=True)
            (final/'device-profile.json').write_text('{}');(final/'cache.bin').write_bytes(b'x')
            self.assertFalse(is_logged_out(final))
            with self.assertRaises(FileExistsError):commit_session(stage,final,root/'pending'/'owner')
            self.assertEqual(sorted(p.name for p in final.iterdir()),['cache.bin','device-profile.json'])
            self.assertTrue((stage/'session.db').exists())
    def test_failed_publish_restores_kept_profile(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); stage=root/'staging';stage.mkdir();(stage/'session.db').write_bytes(b'new')
            final=root/'sessions'/'owner';final.mkdir(parents=True);(final/'device-profile.json').write_text('{"profile": 1}')
            marker=root/'pending'/'owner'
            real_open=Path.open
            def failing_open(self,*args,**kwargs):
                if self==marker:raise OSError('disk full')
                return real_open(self,*args,**kwargs)
            with patch.object(Path,'open',failing_open):
                with self.assertRaises(OSError):commit_session(stage,final,marker)
            self.assertEqual((final/'device-profile.json').read_text(),'{"profile": 1}')
            self.assertEqual(sorted(p.name for p in final.iterdir()),['device-profile.json'])
            self.assertEqual((stage/'session.db').read_bytes(),b'new')
            self.assertFalse(marker.exists())
    def test_pending_marker_blocks_new_login(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); marker=root/'pending'/'owner';marker.parent.mkdir();marker.write_text('ready')
            self.assertTrue(session_in_use(root/'sessions'/'owner',marker))
            self.assertFalse(session_in_use(root/'sessions'/'owner',root/'pending'/'other'))

if __name__ == '__main__':unittest.main()
