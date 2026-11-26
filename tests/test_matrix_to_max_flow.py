import unittest
from types import SimpleNamespace as O
from unittest.mock import AsyncMock, MagicMock
from mautrix.types import TextMessageEventContent, MediaMessageEventContent,MessageType,ContentURI,FileInfo
from mautrix_max.portal import Portal

class MatrixToMaxFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.portal=Portal.__new__(Portal)
        self.portal.is_direct=False;self.portal.receiver=None;self.portal.chat_id='42'
        self.portal._max_reply_target=AsyncMock(return_value=None)
        self.portal._store_outgoing_mapping=AsyncMock()
        self.sent=O(id=99,chat_id=42,time=100,sender=2,text='sample',attaches=[])
        self.wrapper=O(is_ready=True,send_message=AsyncMock(return_value=self.sent),send_media=AsyncMock(return_value=self.sent))
        self.sender=O(mxid='@owner:test',max_client=self.wrapper,archive_message=AsyncMock(return_value=True))
    async def test_text_is_sent_mapped_and_archived(self):
        event=TextMessageEventContent(msgtype=MessageType.TEXT,body='sample')
        await self.portal.handle_matrix_message(self.sender,event,'$event:test')
        self.wrapper.send_message.assert_awaited_once_with(chat_id=42,text='sample',reply_to=None)
        self.portal._store_outgoing_mapping.assert_awaited_once_with('$event:test',self.sent)
        self.sender.archive_message.assert_awaited_once_with(self.sent,chat_id_override=42)
    async def test_file_is_downloaded_sent_mapped_and_archived(self):
        intent=O(download_media=AsyncMock(return_value=b'abc'))
        self.portal._matrix_download_intent=AsyncMock(return_value=intent)
        self.portal._media_max_size=MagicMock(return_value=10)
        event=MediaMessageEventContent(msgtype=MessageType.FILE,body='test.txt',filename='test.txt',url=ContentURI('mxc://test/file'),info=FileInfo(mimetype='text/plain',size=3))
        await self.portal.handle_matrix_message(self.sender,event,'$file:test')
        self.wrapper.send_media.assert_awaited_once_with(chat_id=42,data=b'abc',filename='test.txt',kind='file',caption='',reply_to=None)
        self.portal._store_outgoing_mapping.assert_awaited_once_with('$file:test',self.sent)
        self.sender.archive_message.assert_awaited_once_with(self.sent,chat_id_override=42)
