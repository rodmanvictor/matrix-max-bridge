import unittest
from types import SimpleNamespace as O
from unittest.mock import AsyncMock, MagicMock
from mautrix_max.local_search import search_history
from mautrix_max.user import User

class ArchiveIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_history_indexes_even_messages_that_do_not_match_query(self):
        messages=[O(id=1,text='apple',time=100,sender=5,attaches=[]),O(id=2,text='banana',time=101,sender=5,attaches=[])]
        client=O(fetch_history=AsyncMock(return_value=messages))
        archive=O(save_messages=AsyncMock(return_value=2))
        result=await search_history(client,42,'apple',pages=1,archive=archive,owner='@a:test')
        archive.save_messages.assert_awaited_once_with('@a:test',42,messages)
        self.assertEqual(result['indexed'],2)
        self.assertEqual([x['id'] for x in result['messages']],[1])
    async def test_user_archives_received_message_without_affecting_forwarding_on_db_error(self):
        user=User.__new__(User);user.mxid='@a:test'
        archive=O(save_message=AsyncMock(side_effect=RuntimeError('test error')))
        user.bridge=O(archive=archive)
        self.assertFalse(await user.archive_message(O(id=1,chat_id=42)))
        archive.save_message.assert_awaited_once()

    async def test_connect_does_not_start_historical_download(self):
        from unittest.mock import patch
        user=User.__new__(User);user.mxid='@a:test';user._login_in_progress=False;user._db_row=None
        client=O();user.max_client=O(phone='__web_qr__',client=client)
        user.bridge=O(archive=O(save_directory=AsyncMock()))
        user.sync_group_portals=AsyncMock();user.management_room=None
        user._archive_catchup_task=None;user._last_archive_catchup=0.0
        created=[]
        def capture(coroutine):
            created.append(coroutine);coroutine.close();return None
        with patch('mautrix_max.user.asyncio.create_task',side_effect=capture):
            await user.handle_max_ready()
        self.assertEqual(created,[])
