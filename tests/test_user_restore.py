import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from mautrix_max.__main__ import MaxBridge


class UserRestoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_starts_accounts_that_have_no_running_client(self):
        bridge = MaxBridge.__new__(MaxBridge)
        bridge.log = MagicMock()
        bridge._adopt_pending_sessions = AsyncMock()
        waiting = MagicMock(max_client=None, max_phone='__web_qr__')
        waiting.start_max_client = AsyncMock()
        connected = MagicMock(max_client=MagicMock(), max_phone='__web_qr__')
        connected.start_max_client = AsyncMock()
        with patch('mautrix_max.__main__.User.all_logged_in', new=AsyncMock(return_value=[waiting, connected])):
            await bridge._restore_new_users()
        waiting.start_max_client.assert_awaited_once()
        connected.start_max_client.assert_not_awaited()


if __name__ == '__main__': unittest.main()
