import unittest
from unittest.mock import AsyncMock, patch
from mautrix_max.db.portal import Portal

class GroupPortalTests(unittest.IsolatedAsyncioTestCase):
    async def test_group_portal_uses_non_null_storage_key(self):
        db=AsyncMock()
        portal=Portal(db=db,chat_id='123',receiver=None,mxid=None,name=None,is_direct=False)
        await portal.insert()
        self.assertEqual(db.execute.await_args.args[2], '')
        await portal.save()
        self.assertEqual(db.execute.await_args.args[2], '')
    async def test_group_portal_lookup_translates_key(self):
        db=AsyncMock()
        db.fetchrow.return_value={'chat_id':'123','receiver':'','mxid':None,'name':None,'is_direct':False,'remote_user_id':None}
        with patch.object(Portal,'db',db,create=True):
            portal=await Portal.get_by_chat_id('123',None)
        self.assertEqual(db.fetchrow.await_args.args[2], '')
        self.assertIsNone(portal.receiver)
