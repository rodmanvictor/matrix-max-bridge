from __future__ import annotations

import asyncio
import os
from pathlib import Path
from urllib.parse import quote, unquote

from mautrix.bridge import Bridge
from mautrix.types import RoomID, UserID

from . import commands  # noqa: F401
from . import db as db_module
from .config import Config
from .db.upgrade import upgrade_table
from .matrix import MatrixHandler
from .local_rpc import start_rpc
from .db.archive import Archive
from .portal import Portal
from .puppet import Puppet
from .user import User


class MaxBridge(Bridge):
    name = "mautrix-max"
    module = "mautrix_max"
    command = "python -m mautrix_max"
    description = "Неофициальный мост Matrix ↔ MAX через PyMax."
    repo_url = "https://github.com/rodmanvictor/matrix-max-bridge"
    version = "0.14.0"
    config_class = Config
    matrix_class = MatrixHandler
    upgrade_table = upgrade_table

    def prepare_config(self) -> None:
        super().prepare_config()
        User.config = self.config

    def prepare_bridge(self) -> None:
        super().prepare_bridge()
        User.az = self.az
        User.bridge = self
        User.loop = self.loop

        Portal.az = self.az
        Portal.bridge = self
        Portal.matrix = self.matrix
        Portal.loop = self.loop

        Puppet.az = self.az
        Puppet.mx = self.matrix
        Puppet.loop = self.loop

    def prepare_db(self) -> None:
        super().prepare_db()
        db_module.init(self.db)
        self.archive = Archive(self.db)

    async def get_user(self, user_id: UserID, create: bool = True):
        return await User.get_by_mxid(user_id, create=create)

    async def get_portal(self, room_id: RoomID):
        return await Portal.get_by_mxid(room_id)

    async def get_puppet(self, user_id: UserID, create: bool = False):
        max_id = Puppet.get_id_from_mxid(user_id)
        if not max_id:
            return None
        return await Puppet.get_by_max_id(max_id, create=create)

    async def get_double_puppet(self, user_id: UserID):
        return await Puppet.get_by_custom_mxid(user_id)

    def is_bridge_ghost(self, user_id: UserID) -> bool:
        return Puppet.get_id_from_mxid(user_id) is not None

    async def count_logged_in_users(self) -> int:
        return len(
            [
                user
                for user in User.by_mxid.values()
                if user.max_client is not None and user.max_client.is_ready
            ]
        )

    async def _adopt_pending_sessions(self) -> None:
        root = Path(self.config["bridge.max.session_dir"] or "./sessions")
        pending = root.parent / "pending"
        if not pending.is_dir():
            return
        domain = self.config["homeserver.domain"]
        for marker in pending.iterdir():
            mxid = unquote(marker.name)
            if not marker.is_file() or quote(mxid, safe="") != marker.name:
                continue
            if not mxid.startswith("@") or not mxid.endswith(":" + domain):
                continue
            if not self.config.get_permissions(mxid)[2]:
                continue
            session = root / marker.name / "session.db"
            if not session.is_file():
                continue
            user = await User.get_by_mxid(UserID(mxid))
            row = user._db_row
            if row is None or (row.max_phone and row.max_phone != "__web_qr__"):
                self.log.warning("Refusing to replace an existing MAX session")
                continue
            row.max_phone = "__web_qr__"
            row.max_session_file = str(session)
            await row.save()
            user.max_phone = row.max_phone
            marker.unlink()

    async def _restore_new_users(self) -> None:
        # A QR bootstrap may add a user after the bridge has already started.
        await self._adopt_pending_sessions()
        for user in await User.all_logged_in():
            if user.max_client is not None:
                continue
            try:
                await user.start_max_client()
            except Exception:
                self.log.exception("Could not start a configured MAX session")

    async def _watch_new_users(self) -> None:
        while True:
            await asyncio.sleep(15)
            try:
                await self._restore_new_users()
            except Exception:
                self.log.exception("MAX session discovery failed")

    async def start(self) -> None:
        await super().start()
        await self._restore_new_users()
        owner = os.environ.get("MAX_RPC_MXID")
        self._local_rpc = None
        if owner:
            if not self.config.get_permissions(owner)[2]:
                raise RuntimeError("Local MAX RPC owner must be whitelisted")
            self._local_rpc = await start_rpc(
                Path(os.environ.get("MAX_RPC_SOCKET", "/data/run/max.sock")), lambda: User.by_mxid.get(UserID(owner)), self.archive
            )
        self._watch_task = self.loop.create_task(self._watch_new_users())

    async def stop(self) -> None:
        task = getattr(self, "_watch_task", None)
        if task:
            task.cancel()
        runner = getattr(self, "_local_rpc", None)
        if runner:
            await runner.cleanup()
        await super().stop()


def main() -> None:
    MaxBridge().run()


if __name__ == "__main__":
    main()
