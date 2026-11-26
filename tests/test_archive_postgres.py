"""Run against an explicitly supplied disposable PostgreSQL database."""
import os
import unittest
from pathlib import Path
from types import SimpleNamespace as O
from urllib.parse import quote
from mautrix.util.async_db import Database
from mautrix_max.db.archive import Archive
from mautrix_max.db.upgrade import upgrade_table

@unittest.skipUnless(os.environ.get('MAX_TEST_DATABASE'), 'requires disposable PostgreSQL database')
class PostgresArchiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_postgres_writes_queries_and_resume(self):
        password=Path('/run/secrets/max_db_password').read_text().strip()
        database=os.environ['MAX_TEST_DATABASE']
        url='postgresql://mautrix_max:'+quote(password,safe='')+'@postgres:5432/'+database
        db=Database.create(url, upgrade_table=upgrade_table)
        await db.start()
        try:
            a=Archive(db)
            await a.save_message('@a:example.org',7,O(id=8,time=100,sender=3,text='План',attaches=[]))
            self.assertEqual(len((await a.search_messages('@a:example.org','план'))['messages']),1)
            self.assertEqual(len((await a.search_messages('@a:example.org','план',chat_id=8))['messages']),0)
            await a.save_checkpoint('@a:example.org',7,100,1,1)
            await a.save_checkpoint('@a:example.org',7,50,2,3)
            self.assertEqual((await a.get_checkpoint('@a:example.org',7))['pages'],3)
        finally:await db.stop()
