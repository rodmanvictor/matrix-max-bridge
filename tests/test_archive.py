import tempfile
import unittest
from types import SimpleNamespace as O
from pathlib import Path
from mautrix.util.async_db import Database
from mautrix_max.db.archive import Archive
from mautrix_max.db.upgrade import upgrade_v11, upgrade_v12

class ArchiveTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Database.create('sqlite:///'+str(Path(self.tmp.name)/'test.db'))
        await self.db.start()
        async with self.db.acquire() as conn: await upgrade_v11(conn,None); await upgrade_v12(conn,None)
        self.archive=Archive(self.db)
    async def asyncTearDown(self):
        await self.db.stop();self.tmp.cleanup()
    async def test_persists_deduplicates_searches_and_isolates_accounts(self):
        msg=O(id=3,time=123,sender=9,text='Отправь ПЛАН',attaches=[O(name='Смета.PDF',token='private-value')])
        await self.archive.save_message('@alice:test',42,msg)
        await self.archive.save_message('@alice:test',42,msg)
        await self.archive.save_message('@bob:test',42,O(id=4,time=124,sender=8,text='Отправь план',attaches=[]))
        rows=await self.archive.search_messages('@alice:test','план')
        self.assertEqual([r['id'] for r in rows['messages']],['3'])
        self.assertTrue(rows['partial'])
        self.assertNotIn('private-value',repr(rows))
        files=await self.archive.search_messages('@alice:test','смета')
        self.assertEqual(files['messages'][0]['files'][0]['name'],'Смета.PDF')
    async def test_literal_wildcards_do_not_match_everything(self):
        await self.archive.save_message('@a:test',5,O(id=1,time=1,sender=None,text='plain',attaches=[]))
        self.assertEqual((await self.archive.search_messages('@a:test','%'))['messages'],[])
    async def test_existing_message_updates_and_history_order(self):
        await self.archive.save_message('@a:test',5,O(id=1,time=1,sender=2,text='old',attaches=[]))
        await self.archive.save_message('@a:test',5,O(id=1,time=1,sender=2,text='new',attaches=[]))
        self.assertEqual((await self.archive.search_messages('@a:test','old'))['messages'],[])
        self.assertEqual((await self.archive.search_messages('@a:test','new'))['messages'][0]['id'],'1')
    async def test_checkpoints_are_scoped_and_never_claim_complete_history(self):
        await self.archive.save_checkpoint('@a:test',42,100,2,150)
        await self.archive.save_checkpoint('@a:test',42,50,1,70)
        checkpoint=await self.archive.get_checkpoint('@a:test',42)
        self.assertEqual(checkpoint['next_before_ms'],50)
        self.assertEqual(checkpoint['pages'],3)
        self.assertEqual(checkpoint['scanned'],220)
        self.assertTrue(checkpoint['partial'])
        self.assertIsNone(await self.archive.get_checkpoint('@b:test',42))
    async def test_newer_refresh_does_not_move_history_cursor_forward(self):
        await self.archive.save_checkpoint('@a:test',42,50,1,100)
        await self.archive.save_checkpoint('@a:test',42,900,1,10)
        self.assertEqual((await self.archive.get_checkpoint('@a:test',42))['next_before_ms'],50)
    async def test_status_reports_indexed_counts_without_private_content(self):
        await self.archive.save_message('@a:test',5,O(id=1,time=1,sender=2,text='private text',attaches=[]))
        status=await self.archive.status('@a:test')
        self.assertEqual(status['messages'],1)
        self.assertEqual(status['indexed_chats'],1)
        self.assertNotIn('private text',repr(status))
    async def test_contact_and_chat_search_remain_account_scoped(self):
        contact=O(id=8,names=[O(name='Анна Спирина',first_name='Анна',last_name='Спирина')])
        client=O(contacts=[contact],chats=[O(id=55,title='Рабочая группа',type='CHAT')],me=O(contact=O(id=1)),get_chat_id=lambda a,b:99)
        await self.archive.save_directory('@a:test',client)
        self.assertEqual((await self.archive.search_directory('@a:test','анна','contact'))['matches'][0]['chat_id'], '99')
        self.assertEqual((await self.archive.search_directory('@a:test','РАБОЧ','chat'))['matches'][0]['id'], '55')
        self.assertEqual((await self.archive.search_directory('@b:test','анна','contact'))['matches'],[])
