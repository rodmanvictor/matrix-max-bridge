import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from mautrix_max import max_client


class WebSessionTests(unittest.TestCase):
    def test_web_marker_uses_web_client_without_phone_or_debug_logging(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(max_client, 'WebClient', create=True) as web, \
             patch.object(max_client, 'Client') as mobile:
            web.return_value = MagicMock()
            wrapper = max_client.MaxClientWrapper(
                phone='__web_qr__', work_dir=directory, on_message=MagicMock()
            )
            mobile.assert_not_called()
            web.assert_called_once()
            kwargs = web.call_args.kwargs
            self.assertEqual(kwargs['work_dir'], directory)
            self.assertNotEqual(kwargs['extra_config'].log_level, 'DEBUG')
            self.assertFalse(kwargs['extra_config'].telemetry)
            self.assertFalse(kwargs['extra_config'].relogin)
            self.assertEqual(kwargs['extra_config'].sync.chats_sync, -1)
            self.assertEqual(kwargs['extra_config'].sync.contacts_sync, -1)
            self.assertIs(wrapper.client, web.return_value)

    def test_session_diagnostics_do_not_read_session_token(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'session.db').touch()
            wrapper = max_client.MaxClientWrapper.__new__(max_client.MaxClientWrapper)
            wrapper.work_dir = directory
            wrapper.client = MagicMock()
            with patch.object(max_client.sqlite3, 'connect', side_effect=AssertionError('session was read')):
                result = wrapper._session_diagnostics()
            self.assertNotIn('token', repr(result).lower())


if __name__ == '__main__':
    unittest.main()
