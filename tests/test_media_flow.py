import asyncio
import unittest
from types import SimpleNamespace as O
from unittest.mock import AsyncMock, MagicMock
from pymax import File, Photo, Video
from pymax.types import FileAttachment
from mautrix_max.max_client import MaxClientWrapper

class MediaFlowTests(unittest.IsolatedAsyncioTestCase):
    def wrapper(self):
        w=MaxClientWrapper.__new__(MaxClientWrapper)
        w._ready=asyncio.Event();w._ready.set();w._last_error=None
        w.client=O(_app=O(started=True),send_message=AsyncMock(return_value=O(id=7)),get_file_by_id=AsyncMock(return_value=O(url='https://example.invalid/file')))
        w._task=MagicMock();w._task.done.return_value=False
        return w
    async def test_outgoing_attachment_uses_pymax_25_types(self):
        w=self.wrapper()
        for kind,cls in [('file',File),('image',Photo),('video',Video)]:
            await w.send_media(1,b'abc','test.jpg',kind,'caption')
            sent=w.client.send_message.await_args.kwargs
            self.assertIsInstance(sent['attachments'][0],cls)
            self.assertEqual(await sent['attachments'][0].read(),b'abc')
            self.assertEqual(sent['text'],'caption')
    async def test_incoming_file_is_resolved_and_downloaded(self):
        w=self.wrapper();w._download_url=AsyncMock(return_value=(b'abc','file.txt','text/plain'))
        att=FileAttachment.model_validate({'_type':'FILE','fileId':8,'name':'file.txt','size':3,'token':'fake'})
        result=await w.download_attachment(O(chat_id=1,id=2),att,max_size=100)
        w.client.get_file_by_id.assert_awaited_once_with(1,2,8)
        self.assertEqual(result.data,b'abc')
        self.assertEqual(result.filename,'file.txt')
