import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as O
from unittest.mock import AsyncMock
from aiohttp import ClientSession, UnixConnector
from mautrix_max.local_rpc import start_rpc

class LocalRPCTests(unittest.IsolatedAsyncioTestCase):
    async def test_socket_search_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            user=O(max_client=O(is_ready=True,client=O(contacts=[O(id=1,names=[O(name='Anna', first_name=None,last_name=None)])])))
            runner=await start_rpc(path, lambda:user)
            try:
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.get('http://localhost/contacts',params={'q':'anna'}) as response:
                        self.assertEqual(response.status,200)
                        self.assertEqual((await response.json())['matches'][0]['id'],1)
                    async with session.get('http://localhost/contacts') as response:
                        self.assertEqual(response.status,400)
            finally:
                await runner.cleanup()
    async def test_download_is_binary_and_attachment_is_selected_by_index(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            msg=O(chat_id=1,id=2,attaches=[O()])
            wrapper=O(is_ready=True,client=O(get_message=AsyncMock(return_value=msg)),download_attachment=AsyncMock(return_value=O(data=b'test-file')))
            runner=await start_rpc(path, lambda:O(max_client=wrapper))
            try:
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.get('http://localhost/attachment?chat=1&message=2&index=0') as response:
                        self.assertEqual(response.status,200)
                        self.assertEqual(await response.read(),b'test-file')
                wrapper.download_attachment.assert_awaited_once()
            finally: await runner.cleanup()
    async def test_archive_search_works_when_max_is_disconnected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            archive=O(search_messages=AsyncMock(return_value={'messages':[{'id':'1'}],'partial':True}))
            user=O(mxid='@owner:test', max_client=None)
            runner=await start_rpc(path,lambda:user,archive)
            try:
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.get('http://localhost/archive/messages?q=test') as response:
                        self.assertEqual(response.status,200)
                        self.assertEqual((await response.json())['messages'][0]['id'],'1')
                    async with session.get('http://localhost/contacts?q=test') as response:
                        self.assertEqual(response.status,503)
            finally:await runner.cleanup()
    async def test_index_resumes_saved_cursor_and_persists_new_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            archive=O(get_checkpoint=AsyncMock(return_value={'next_before_ms':500}),save_checkpoint=AsyncMock(),save_messages=AsyncMock(return_value=1))
            msg=O(id=1,text='sample',time=400,sender=7,attaches=[])
            client=O(fetch_history=AsyncMock(return_value=[msg]))
            user=O(mxid='@owner:test',max_client=O(is_ready=True,client=client))
            runner=await start_rpc(path,lambda:user,archive)
            try:
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.post('http://localhost/index?chat=7&pages=1') as response:
                        self.assertEqual(response.status,200)
                        payload=await response.json()
                self.assertNotIn('messages',payload)
                self.assertEqual(client.fetch_history.await_args.kwargs['from_time'],500)
                archive.save_checkpoint.assert_awaited_once_with('@owner:test',7,399,1,1)
            finally:await runner.cleanup()
    async def test_index_chat_list_is_bounded_and_does_not_include_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            chat=O(id=42,title='Example',type='CHAT',token='secret')
            user=O(mxid='@owner:test',max_client=O(is_ready=True,client=O(chats=[chat])))
            runner=await start_rpc(path,lambda:user,O())
            try:
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.get('http://localhost/index/chats?limit=10') as response:
                        self.assertEqual(response.status,200)
                        data=await response.json()
                self.assertEqual(data['chats'][0]['id'],42)
                self.assertNotIn('secret',repr(data))
                self.assertTrue(data['partial'])
            finally:await runner.cleanup()
    async def test_chat_list_pagination_has_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            chats=[O(id=i,title='chat',type='CHAT') for i in (1,2,3)]
            user=O(mxid='@owner:test',max_client=O(is_ready=True,client=O(chats=chats)))
            runner=await start_rpc(Path(directory)/'rpc.sock',lambda:user,O())
            try:
                async with ClientSession(connector=UnixConnector(path=str(Path(directory)/'rpc.sock'))) as session:
                    async with session.get('http://localhost/index/chats?limit=1&offset=1') as response:
                        result=await response.json()
                self.assertEqual(result['chats'][0]['id'],2)
                self.assertEqual(result['next_offset'],2)
            finally:await runner.cleanup()
    async def test_fresh_index_starts_at_present(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            archive=O(get_checkpoint=AsyncMock(return_value={'next_before_ms':500}),save_checkpoint=AsyncMock(),save_messages=AsyncMock(return_value=0))
            client=O(fetch_history=AsyncMock(return_value=[]))
            user=O(mxid='@owner:test',max_client=O(is_ready=True,client=client))
            runner=await start_rpc(path,lambda:user,archive)
            try:
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.post('http://localhost/index?chat=7&fresh=1') as response:
                        self.assertEqual(response.status,200)
                self.assertIsNone(client.fetch_history.await_args.kwargs['from_time'])
            finally:await runner.cleanup()
    async def test_remote_failure_returns_generic_json_without_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            client=O(fetch_history=AsyncMock(side_effect=RuntimeError('private token example')))
            user=O(mxid='@owner:test',max_client=O(is_ready=True,client=client))
            runner=await start_rpc(path,lambda:user,O())
            try:
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.get('http://localhost/history?chat=1&read=1') as response:
                        self.assertEqual(response.status,503)
                        data=await response.json()
                self.assertNotIn('private token example',repr(data))
            finally:await runner.cleanup()
    async def test_refresh_chat_directory_updates_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            client=O(fetch_chats=AsyncMock(return_value=[O(id=1)]))
            user=O(mxid='@owner:test',max_client=O(is_ready=True,client=client))
            archive=O(save_directory=AsyncMock(return_value=2))
            runner=await start_rpc(path,lambda:user,archive)
            try:
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.post('http://localhost/directory/refresh') as response:
                        self.assertEqual(response.status,200);data=await response.json()
                self.assertEqual(data['fetched'],1)
                archive.save_directory.assert_awaited_once_with('@owner:test',client)
            finally:await runner.cleanup()
    async def test_refuses_to_replace_regular_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock';path.write_text('do not erase')
            with self.assertRaises(RuntimeError): await start_rpc(path,lambda:None)
            self.assertEqual(path.read_text(),'do not erase')

class DelayedMessageTests(unittest.IsolatedAsyncioTestCase):
    """Native MAX delayed messages through the local socket."""
    def _user(self, delayed=None):
        sent=O(id=77,text='hello',attaches=[],delayed_attributes=O(time_to_fire=1))
        client=O(send_message=AsyncMock(return_value=sent),delete_message=AsyncMock(return_value=True),
                 fetch_history=AsyncMock(side_effect=delayed if delayed is not None else [[sent]]))
        return O(mxid='@owner:test',max_client=O(is_ready=True,client=client)),client
    async def _call(self,user,method,url,**kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'rpc.sock'
            runner=await start_rpc(path,lambda:user)
            try:
                async with ClientSession(connector=UnixConnector(path=str(path))) as session:
                    async with session.request(method,'http://localhost'+url,**kwargs) as response:
                        return response.status,await response.json()
            finally:await runner.cleanup()
    async def test_text_is_scheduled_with_absolute_utc_time(self):
        import time
        from datetime import timezone
        user,client=self._user()
        at=int(time.time())+3600
        status,data=await self._call(user,'POST',f'/delayed/send?chat=5&at={at}&kind=text',data='привет'.encode())
        self.assertEqual(status,200)
        self.assertEqual(data['id'],77)
        self.assertNotIn('text',data)
        kwargs=client.send_message.await_args.kwargs
        self.assertEqual(kwargs['chat_id'],5)
        self.assertEqual(kwargs['text'],'привет')
        self.assertEqual(kwargs['send_at'].tzinfo,timezone.utc)
        self.assertEqual(int(kwargs['send_at'].timestamp()),at)
    async def test_body_larger_than_the_app_limit_is_accepted_for_files(self):
        import time
        user,client=self._user()
        at=int(time.time())+3600
        payload=b'x'*5000
        status,_=await self._call(user,'POST',f'/delayed/send?chat=5&at={at}&kind=file&name=..%2Fdoc.pdf',data=payload)
        self.assertEqual(status,200)
        kwargs=client.send_message.await_args.kwargs
        self.assertIsNone(kwargs['text'])
        attachment=kwargs['attachments'][0]
        self.assertEqual(attachment.name,'doc.pdf')
        self.assertEqual(attachment.raw,payload)
    async def test_rejects_past_time_missing_name_and_empty_text(self):
        import time
        user,client=self._user()
        soon=int(time.time())+10
        later=int(time.time())+3600
        for url,body in ((f'/delayed/send?chat=5&at={soon}&kind=text',b'hi'),
                         (f'/delayed/send?chat=5&at={later}&kind=file',b'data'),
                         (f'/delayed/send?chat=5&at={later}&kind=text',b'   '),
                         (f'/delayed/send?chat=5&at={later}&kind=audio',b'hi'),
                         (f'/delayed/send?chat=x&at={later}',b'hi')):
            status,data=await self._call(user,'POST',url,data=body)
            self.assertEqual(status,400,url)
            self.assertIn('error',data)
        client.send_message.assert_not_awaited()
    async def test_list_requests_delayed_items_from_the_future(self):
        import time
        user,client=self._user()
        status,data=await self._call(user,'GET','/delayed?chat=5')
        self.assertEqual(status,200)
        self.assertEqual(data['delayed'][0]['id'],77)
        kwargs=client.fetch_history.await_args.kwargs
        self.assertEqual(str(kwargs['item_type'].value),'DELAYED')
        self.assertGreater(kwargs['from_time'],int(time.time()*1000))
        self.assertEqual(data['query'],'backward-from-horizon')
    async def test_list_tries_other_request_shapes_and_ignores_regular_messages(self):
        sent=O(id=77,text='hello',attaches=[],delayed_attributes=O(time_to_fire=1))
        regular=O(id=5,text='old',attaches=[],delayed_attributes=None)
        user,client=self._user(delayed=[[],[regular],[sent]])
        status,data=await self._call(user,'GET','/delayed?chat=-9')
        self.assertEqual(status,200)
        self.assertEqual([item['id'] for item in data['delayed']],[77])
        self.assertEqual(data['query'],'both-from-now')
        self.assertEqual(client.fetch_history.await_count,3)
    async def test_cancel_names_the_delayed_item_type_and_checks_the_list(self):
        sent=O(id=77,text='hello',attaches=[],delayed_attributes=O(time_to_fire=1))
        user,client=self._user(delayed=[[sent],[]])
        client._app=O(invoke=AsyncMock())
        status,data=await self._call(user,'POST','/delayed/cancel?chat=5&message=77')
        self.assertEqual(status,200)
        self.assertTrue(data['cancelled'])
        self.assertEqual(data['method'],'itemType')
        payload=client._app.invoke.await_args.args[1]
        self.assertEqual(payload,{'chatId':5,'messageIds':[77],'forMe':False,'itemType':'DELAYED'})
    async def test_cancel_reports_failure_and_rejects_unknown_message(self):
        sent=O(id=77,text='hello',attaches=[],delayed_attributes=O(time_to_fire=1))
        user,client=self._user(delayed=[[sent],[sent],[sent],[sent]])
        client._app=O(invoke=AsyncMock())
        status,data=await self._call(user,'POST','/delayed/cancel?chat=5&message=77')
        self.assertEqual(status,200)
        self.assertFalse(data['cancelled'])
        self.assertEqual(client._app.invoke.await_count,3)
        user,client=self._user(delayed=[[sent]])
        client._app=O(invoke=AsyncMock())
        status,data=await self._call(user,'POST','/delayed/cancel?chat=5&message=78')
        self.assertEqual(status,400)
        client._app.invoke.assert_not_awaited()
