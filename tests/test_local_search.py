import unittest
from types import SimpleNamespace as O
from unittest.mock import AsyncMock
from mautrix_max.local_search import search_contacts, search_chats, search_history, read_history

class LocalSearchTests(unittest.IsolatedAsyncioTestCase):
    def test_contacts_returns_all_matches_to_avoid_guessing(self):
        client=O(contacts=[O(id=1,names=[O(name='Вероника Петрова',first_name=None,last_name=None)]),O(id=2,names=[O(name='Вероника Сидорова',first_name=None,last_name=None)]),O(id=3,names=[])])
        result=search_contacts(client,'вероника')
        self.assertEqual([c['id'] for c in result['matches']],[1,2])
        self.assertTrue(result['partial'])
    def test_contact_results_include_existing_dialog_id_when_possible(self):
        client=O(contacts=[O(id=42,names=[O(name='Анна',first_name=None,last_name=None)])], me=O(contact=O(id=1)), get_chat_id=lambda own, other: 99)
        self.assertEqual(search_contacts(client,'анна')['matches'][0]['chat_id'],99)
    def test_chats_search_is_case_insensitive(self):
        client=O(chats=[O(id=1,title='Рабочая группа',type='CHAT'),O(id=2,title='Другой',type='CHAT')])
        self.assertEqual(search_chats(client,'РАБОЧ')["matches"][0]['id'],1)
    async def test_history_is_bounded_and_marks_partial(self):
        client=O(fetch_history=AsyncMock(return_value=[O(id=4,text='Отправь файл',time=123,sender=5,attaches=[])]))
        result=await search_history(client,42,'ФАЙЛ',pages=1)
        self.assertEqual(result['messages'][0]['id'],4)
        self.assertEqual(result['scanned'],1)
        self.assertTrue(result['partial'])
        client.fetch_history.assert_awaited_once()
    async def test_history_searches_file_names_without_returning_file_tokens(self):
        client=O(fetch_history=AsyncMock(return_value=[O(id=5,text='',time=123,sender=5,attaches=[O(name='План.xlsx',token='private')])]))
        result=await search_history(client,42,'план',pages=1)
        self.assertEqual(result['messages'][0]['file_names'], ['План.xlsx'])
        self.assertNotIn('private', repr(result))
    async def test_read_recent_messages_without_search_term_and_with_cursor(self):
        client=O(fetch_history=AsyncMock(return_value=[O(id=5,text='Просьба',time=123,sender=5,attaches=[])]))
        result=await read_history(client,42,pages=1,before=999)
        self.assertEqual(result['messages'][0]['text'], 'Просьба')
        self.assertEqual(client.fetch_history.await_args.kwargs['from_time'],999)
    async def test_history_rejects_unbounded_or_empty_search(self):
        with self.assertRaises(ValueError): await search_history(O(),1,'',pages=1)
        with self.assertRaises(ValueError): await search_history(O(),1,'x',pages=1000)
