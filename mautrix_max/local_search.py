"""Bounded, read-only searches against the active MAX session."""
from __future__ import annotations
import asyncio

def _term(query: str) -> str:
    query = str(query).strip().casefold()
    if not query or len(query) > 256:
        raise ValueError('search query must have 1..256 characters')
    return query

def search_contacts(client, query: str) -> dict:
    term = _term(query)
    matches = []
    for contact in client.contacts or []:
        if contact is None:
            continue
        names = []
        for name in contact.names:
            names.extend(x for x in (name.name, name.first_name, name.last_name,
                ' '.join(x for x in (name.first_name, name.last_name) if x)) if x)
        if any(term in value.casefold() for value in names):
            entry = {'id': contact.id, 'names': list(dict.fromkeys(names))}
            own_id = getattr(getattr(getattr(client, 'me', None), 'contact', None), 'id', None)
            if own_id is not None and callable(getattr(client, 'get_chat_id', None)):
                entry['chat_id'] = client.get_chat_id(int(own_id), int(contact.id))
            matches.append(entry)
    return {'matches': matches[:100], 'partial': True, 'scope': 'cached MAX contacts'}

def search_chats(client, query: str) -> dict:
    term = _term(query)
    matches = [{'id': chat.id, 'title': chat.title, 'type': str(chat.type)}
        for chat in client.chats or [] if chat.title and term in chat.title.casefold()]
    return {'matches': matches[:100], 'partial': True, 'scope': 'cached MAX chats'}

async def search_history(client, chat_id: int, query: str, pages: int = 1, before: int | None = None, *, archive=None, owner=None) -> dict:
    return await _history(client, chat_id, _term(query), pages, before, archive, owner)

async def read_history(client, chat_id: int, pages: int = 1, before: int | None = None, *, archive=None, owner=None) -> dict:
    return await _history(client, chat_id, None, pages, before, archive, owner)

async def _history(client, chat_id: int, term: str | None, pages: int, before: int | None, archive, owner) -> dict:
    if before is not None and before <= 0:
        raise ValueError('before must be positive')
    if not 1 <= pages <= 5:
        raise ValueError('pages must be between 1 and 5')
    cursor = before
    seen = set()
    result = []
    count = 0
    indexed = 0
    pages_fetched = 0
    for _ in range(pages):
        messages = await asyncio.wait_for(client.fetch_history(chat_id=chat_id, backward=100, from_time=cursor), timeout=30)
        pages_fetched += 1
        if not messages:
            break
        fresh = [m for m in messages if m.id not in seen]
        if not fresh:
            break
        if archive is not None and owner is not None:
            indexed += await archive.save_messages(owner,chat_id,fresh)
        for message in fresh:
            seen.add(message.id)
            count += 1
            files = [{'index':i,'name':a.name} for i,a in enumerate(message.attaches or []) if isinstance(getattr(a, 'name', None), str)]
            filenames = [a['name'] for a in files]
            if term is None or term in (message.text or '').casefold() or any(term in name.casefold() for name in filenames):
                result.append({'id':message.id,'chat_id':chat_id,'sender':message.sender,
                    'time':message.time,'text':message.text,'file_names':filenames,'files':files,'attachments':len(message.attaches or [])})
        times = [m.time for m in fresh if m.time]
        if not times:
            break
        next_cursor = min(times) - 1
        if cursor is not None and next_cursor >= cursor:
            break
        cursor = next_cursor
    return {'messages': result, 'scanned': count, 'indexed': indexed, 'pages_fetched': pages_fetched, 'partial': True,
            'next_before_ms': cursor,
            'scope': 'bounded MAX history; older messages or same-timestamp messages may be omitted'}
