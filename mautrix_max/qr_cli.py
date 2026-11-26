"""One-shot interactive MAX Web login; secrets are only shown on the TTY."""
from __future__ import annotations
import asyncio
import getpass
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import qrcode
from pymax import ExtraConfig, QrAuthFlow, WebClient
from .qr_bootstrap import commit_session

os.umask(0o077)

class TerminalAuth:
    async def show_qr(self, value: str) -> None:
        print('\nОтсканируйте QR-код в приложении MAX:\n', flush=True)
        code = qrcode.QRCode(border=1)
        code.add_data(value)
        code.make(fit=True)
        code.print_ascii(tty=False, invert=True)
        print('\nОжидаем подтверждение в MAX…', flush=True)

    async def get_password(self, hint: str | None = None) -> str:
        return await asyncio.to_thread(getpass.getpass, 'Пароль MAX: ')

async def run() -> None:
    owner = os.environ.get('MAX_AUTH_MXID', '')
    if not re.fullmatch(r'@[a-z0-9._=\-/]+:[a-z0-9.-]+', owner):
        raise RuntimeError('Некорректная учётная запись Matrix')
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError('Требуется интерактивный терминал')
    # Must be the parent of bridge.max.session_dir: the bridge adopts sessions from <base>/pending.
    base = Path(os.environ.get('MAX_DATA_DIR', '/data'))
    name = quote(owner, safe='')
    final = base/'sessions'/name
    marker = base/'pending'/name
    if final.exists() or marker.exists():
        raise RuntimeError('Сессия уже существует; обратитесь к администратору')
    stage = Path(tempfile.mkdtemp(prefix='.max-qr-', dir=base))
    authenticated = False
    client = None
    try:
        provider = TerminalAuth()
        client = WebClient(work_dir=str(stage),
            extra_config=ExtraConfig(log_level='WARNING', telemetry=False, reconnect=False, relogin=False),
            auth_flow=QrAuthFlow(qr_provider=provider, password_provider=provider))
        await client.connect()
        authenticated = True
        await client.close()
        client = None
        commit_session(stage, final, marker)
        print('\nАвторизация MAX завершена. Мост подхватит сессию в течение 15 секунд.', flush=True)
    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass
        if stage.exists():
            if authenticated:
                print('Сессия сохранена в защищённом временном каталоге; обратитесь к администратору.', file=sys.stderr)
            else:
                shutil.rmtree(stage)

def main() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print('\nАвторизация отменена.', file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        # Do not print third-party exception details; they may contain sensitive data.
        print(f'Авторизация не завершена ({type(exc).__name__}). Обратитесь к администратору.', file=sys.stderr)
        raise SystemExit(1)

if __name__ == '__main__':
    main()
