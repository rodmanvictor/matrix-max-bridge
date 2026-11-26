import unittest
from unittest.mock import AsyncMock, MagicMock
from mautrix_max.commands import login
from mautrix_max.user import User

class AuthSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_login_does_not_start_chat_based_secret_collection(self):
        event = MagicMock()
        event.args = ['+79990000000']
        event.sender.remember_management_room = AsyncMock()
        event.sender.request_login_code = AsyncMock()
        event.reply = AsyncMock()
        await login(event)
        event.sender.request_login_code.assert_not_awaited()
        self.assertIn('QR', event.reply.await_args.args[0])

    async def test_rejected_session_is_not_deleted(self):
        user = User.__new__(User)
        user._login_in_progress = False
        user.max_phone = '__web_qr__'
        user.max_client = None
        user._db_row = MagicMock()
        user._clear_max_session_data = MagicMock()
        user.management_room = None
        user.mxid = '@owner:example.org'
        await user.handle_max_error(Exception('FAIL_LOGIN_TOKEN'))
        user._clear_max_session_data.assert_not_called()
        self.assertEqual(user.max_phone, '__web_qr__')
