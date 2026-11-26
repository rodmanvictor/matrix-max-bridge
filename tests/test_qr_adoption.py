import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote
from mautrix_max.__main__ import MaxBridge


class FakeConfig(dict):
    def get_permissions(self, mxid): return ("admin", True, True, True)

class QRAdoptionTests(unittest.IsolatedAsyncioTestCase):
    async def test_adopts_completed_session_once(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root); mxid='@owner:example.org';name=quote(mxid,safe='')
            (root/'sessions'/name).mkdir(parents=True);(root/'sessions'/name/'session.db').write_bytes(b'fake')
            (root/'pending').mkdir();(root/'pending'/name).write_text('ready')
            bridge=MaxBridge.__new__(MaxBridge);bridge.config=FakeConfig({'bridge.max.session_dir':str(root/'sessions'),'homeserver.domain':'example.org'});bridge.log=MagicMock()
            row=MagicMock(max_phone=None);row.save=AsyncMock()
            with patch('mautrix_max.__main__.User.get_by_mxid',new=AsyncMock(return_value=MagicMock(_db_row=row))) as get:
                await bridge._adopt_pending_sessions()
            get.assert_awaited_once()
            self.assertEqual(row.max_phone,'__web_qr__')
            row.save.assert_awaited_once()
            self.assertFalse((root/'pending'/name).exists())
    async def test_marker_without_session_is_not_adopted(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);(root/'pending').mkdir();(root/'pending'/'%40owner%3Aexample.org').write_text('ready')
            bridge=MaxBridge.__new__(MaxBridge);bridge.config=FakeConfig({'bridge.max.session_dir':str(root/'sessions'),'homeserver.domain':'example.org'});bridge.log=MagicMock()
            with patch('mautrix_max.__main__.User.get_by_mxid',new=AsyncMock()) as get:
                await bridge._adopt_pending_sessions()
            get.assert_not_awaited()

if __name__ == '__main__':unittest.main()
