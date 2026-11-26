import unittest
from types import SimpleNamespace as O
from unittest.mock import AsyncMock, MagicMock, patch
from mautrix_max.local_rpc import open_contact

class OpenContactTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_unknown_contact_without_opening_chat(self):
        user=O(max_client=O(client=O(contacts=[])))
        with patch('mautrix_max.local_rpc.Puppet') as puppet:
            with self.assertRaises(ValueError):await open_contact(user,42)
            puppet.get_by_max_id.assert_not_called()
    async def test_open_known_contact_without_sending_max_message(self):
        contact=O(id=42)
        client=O(contacts=[contact],me=O(contact=O(id=1)),get_chat_id=MagicMock(return_value=99))
        user=O(mxid='@owner:example.org',max_client=O(client=client))
        puppet=O(name='Test',update_info=AsyncMock())
        portal=O(mxid=None,save=AsyncMock(),create_matrix_room=AsyncMock())
        async def create(**kwargs): portal.mxid='!room:example.org'
        portal.create_matrix_room.side_effect=create
        with patch('mautrix_max.local_rpc.Puppet') as p, patch('mautrix_max.local_rpc.Portal') as po:
            p.get_by_max_id=AsyncMock(return_value=puppet)
            po.get_by_chat_id=AsyncMock(return_value=portal)
            result=await open_contact(user,42)
        self.assertEqual(result['room_id'],'!room:example.org')
        self.assertEqual(result['chat_id'],99)
