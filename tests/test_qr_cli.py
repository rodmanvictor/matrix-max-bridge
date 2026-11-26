import unittest
from unittest.mock import AsyncMock, patch
from mautrix_max.qr_cli import TerminalAuth

class TerminalAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_password_is_read_without_echo_and_not_printed(self):
        provider = TerminalAuth()
        with patch('mautrix_max.qr_cli.getpass.getpass', return_value='test-password') as getpass, patch('builtins.print') as output:
            value = await provider.get_password(None)
        self.assertEqual(value, 'test-password')
        getpass.assert_called_once()
        self.assertNotIn('test-password', repr(output.call_args_list))

    async def test_qr_calls_terminal_renderer(self):
        provider=TerminalAuth()
        with patch('mautrix_max.qr_cli.qrcode.QRCode') as qr, patch('builtins.print'):
            await provider.show_qr('sensitive-example')
        qr.return_value.add_data.assert_called_once_with('sensitive-example')
        qr.return_value.print_ascii.assert_called_once()

class DataDirTests(unittest.IsolatedAsyncioTestCase):
    async def test_data_dir_comes_from_environment(self):
        import os, tempfile
        from pathlib import Path
        from urllib.parse import quote
        from mautrix_max import qr_cli
        with tempfile.TemporaryDirectory() as root:
            active = Path(root)/'sessions'/quote('@owner:example.org', safe='')
            active.mkdir(parents=True); (active/'session.db').write_bytes(b'fake')
            env = {'MAX_AUTH_MXID': '@owner:example.org', 'MAX_DATA_DIR': root}
            with patch.dict(os.environ, env), patch('mautrix_max.qr_cli.sys'):
                with self.assertRaisesRegex(RuntimeError, 'Сессия уже существует'):
                    await qr_cli.run()

    async def test_directory_left_by_logout_does_not_block_login(self):
        import os, tempfile
        from pathlib import Path
        from urllib.parse import quote
        from mautrix_max import qr_cli
        with tempfile.TemporaryDirectory() as root:
            final = Path(root)/'sessions'/quote('@owner:example.org', safe='')
            final.mkdir(parents=True); (final/'device-profile.json').write_text('{}')
            env = {'MAX_AUTH_MXID': '@owner:example.org', 'MAX_DATA_DIR': root}
            class Stop(Exception): pass
            with patch.dict(os.environ, env), patch('mautrix_max.qr_cli.sys'), \
                    patch('mautrix_max.qr_cli.WebClient', side_effect=Stop):
                with self.assertRaises(Stop):
                    await qr_cli.run()
            self.assertEqual([p.name for p in final.iterdir()], ['device-profile.json'])
