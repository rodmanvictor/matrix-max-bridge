"""Local owner-only socket for the account owner's MAX client.

Read operations (search, history, archive) plus native MAX delayed messages:
schedule, list and cancel. The socket is mode 0600; keep it private.
"""
from __future__ import annotations
import asyncio
import os
import logging
import stat
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from aiohttp import web
from .local_search import search_contacts, search_chats, search_history, read_history
from .portal import Portal
from .puppet import Puppet

log = logging.getLogger("mau.max.local_rpc")

async def open_contact(user, contact_id: int) -> dict:
    """Open a local Matrix room for an explicitly selected cached MAX contact."""
    client = user.max_client.client
    contact = next((c for c in (client.contacts or []) if c and c.id == contact_id), None)
    if contact is None:
        raise ValueError("contact not in cached address book")
    own_id = client.me.contact.id
    if own_id == contact_id:
        raise ValueError("cannot open own contact")
    chat_id = client.get_chat_id(int(own_id), int(contact_id))
    puppet = await Puppet.get_by_max_id(str(contact_id))
    await puppet.update_info(contact)
    portal = await Portal.get_by_chat_id(chat_id=str(chat_id), receiver=user.mxid, create=True, is_direct=True)
    created = portal.mxid is None
    portal.is_direct = True
    portal.remote_user_id = str(contact_id)
    portal.name = puppet.name or f"MAX {contact_id}"
    await portal.save()
    if created:
        await portal.create_matrix_room(source=user, dm_puppet=puppet, chat_info=None)
    else:
        await portal.sync_dm_contact_topic(puppet)
    if portal.mxid is None:
        raise RuntimeError("Matrix room not created")
    return {"contact_id": contact_id, "chat_id": chat_id, "room_id": str(portal.mxid), "created": created}

DELAYED_MIN_LEAD_S = 60
DELAYED_MAX_LEAD_S = 366 * 24 * 3600
DELAYED_TEXT_MAX = 16 * 1024
DELAYED_FILE_MAX = 50 * 1024 * 1024
DELAYED_KINDS = ('text', 'image', 'video', 'file')

class DelayedError(Exception):
    """A request problem that is safe to report back to the local caller."""

async def _read_body(request, limit: int) -> bytes:
    """Read the request body as a stream: the app-wide 1 KiB limit stays for other routes."""
    chunks = []
    total = 0
    async for chunk in request.content.iter_chunked(65536):
        total += len(chunk)
        if total > limit:
            raise DelayedError('body is too large')
        chunks.append(chunk)
    return b''.join(chunks)

def _delayed_view(message, chat_id: int) -> dict:
    attributes = getattr(message, 'delayed_attributes', None)
    names = [a.name for a in (getattr(message, 'attaches', None) or []) if isinstance(getattr(a, 'name', None), str)]
    return {'id': getattr(message, 'id', None), 'chat_id': chat_id,
            'time_to_fire_ms': getattr(attributes, 'time_to_fire', None),
            'text': getattr(message, 'text', None), 'file_names': names,
            'attachments': len(getattr(message, 'attaches', None) or [])}

async def send_delayed(user, request) -> dict:
    """Schedule one native MAX delayed message: text, or one attachment without text."""
    client = user.max_client.client
    try:
        chat_id = int(request.query['chat'])
        fire_at = int(request.query['at'])
    except (KeyError, ValueError):
        raise DelayedError('chat and at (Unix seconds) are required integers')
    kind = request.query.get('kind', 'text')
    if kind not in DELAYED_KINDS:
        raise DelayedError('kind must be text, image, video or file')
    lead = fire_at - int(time.time())
    if lead < DELAYED_MIN_LEAD_S:
        raise DelayedError('send time must be at least 60 seconds in the future')
    if lead > DELAYED_MAX_LEAD_S:
        raise DelayedError('send time is too far in the future')
    send_at = datetime.fromtimestamp(fire_at, tz=timezone.utc)
    if kind == 'text':
        body = await _read_body(request, DELAYED_TEXT_MAX)
        try:
            text = body.decode('utf-8').strip()
        except UnicodeDecodeError:
            raise DelayedError('text must be UTF-8')
        if not text:
            raise DelayedError('text must not be empty')
        message = await asyncio.wait_for(client.send_message(chat_id=chat_id, text=text, send_at=send_at), timeout=60)
    else:
        from pymax import File, Photo, Video
        name = PurePosixPath(request.query.get('name', '')).name
        if not name or len(name) > 255:
            raise DelayedError('name is required for an attachment')
        data = await _read_body(request, DELAYED_FILE_MAX)
        if not data:
            raise DelayedError('attachment must not be empty')
        attachment = {'image': Photo, 'video': Video, 'file': File}[kind](raw=data, name=name)
        message = await asyncio.wait_for(
            client.send_message(chat_id=chat_id, text=None, attachments=[attachment], send_at=send_at), timeout=150)
    result = _delayed_view(message, chat_id)
    result.pop('text', None)
    result['requested_at'] = fire_at
    log.info('Scheduled a delayed MAX message: kind=%s lead=%ss', kind, lead)
    return result

async def list_delayed(client, chat_id: int) -> dict:
    """Delayed messages of one chat. MAX returns them only for an explicit DELAYED history request.

    A dialog answers a backward request from a far-future point; a group chat may answer only
    another shape, so several bounded request shapes are tried and `query` names the one that
    returned items. An empty list therefore means "none found", not proof that none exist.
    """
    from pymax.api.messages.enums import ItemType
    now = int(time.time() * 1000)
    horizon = now + (DELAYED_MAX_LEAD_S + 86400) * 1000
    shapes = (
        ('backward-from-horizon', {'from_time': horizon, 'backward': 100, 'forward': 0}),
        ('forward-from-now', {'from_time': now, 'backward': 0, 'forward': 100}),
        ('both-from-now', {'from_time': now, 'backward': 100, 'forward': 100}),
        ('forward-from-start', {'from_time': 1, 'backward': 0, 'forward': 100}),
        ('interactive-from-horizon', {'from_time': horizon, 'backward': 100, 'forward': 0, 'interactive': True}),
    )
    found = {}
    query = None
    for name, shape in shapes:
        try:
            messages = await asyncio.wait_for(
                client.fetch_history(chat_id=chat_id, item_type=ItemType.DELAYED, **shape), timeout=30)
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            log.info('Delayed MAX list shape %s rejected: %s', name, type(exc).__name__)
            continue
        delayed = [m for m in messages or [] if getattr(m, 'delayed_attributes', None) is not None]
        if delayed:
            query = name
            found = {m.id: m for m in delayed}
            break
    items = sorted((_delayed_view(m, chat_id) for m in found.values()), key=lambda item: item['time_to_fire_ms'] or 0)
    return {'delayed': items, 'query': query, 'partial': True, 'scope': 'MAX delayed messages of one chat, at most 100'}

async def cancel_delayed(client, chat_id: int, message_id: int) -> dict:
    """Delete one delayed message, but only if it is still in the chat's delayed list.

    A plain MSG_DELETE is accepted by MAX but leaves a delayed item in place, so the
    request names the item type explicitly. `method` reports which request worked.
    """
    from pymax.protocol import Opcode
    async def listed() -> bool:
        return any(item['id'] == message_id for item in (await list_delayed(client, chat_id))['delayed'])
    if not await listed():
        raise DelayedError('delayed message not found in this chat')
    base = {'chatId': chat_id, 'messageIds': [message_id]}
    attempts = (
        ('itemType', {**base, 'forMe': False, 'itemType': 'DELAYED'}),
        ('itemType+forMe', {**base, 'forMe': True, 'itemType': 'DELAYED'}),
        ('plain', {**base, 'forMe': False}),
    )
    method = None
    for name, payload in attempts:
        try:
            await asyncio.wait_for(client._app.invoke(Opcode.MSG_DELETE, payload), timeout=30)
        except asyncio.TimeoutError:
            raise
        except Exception as exc:
            log.info('Delayed MAX delete variant %s rejected: %s', name, type(exc).__name__)
            continue
        if not await listed():
            method = name
            break
    log.info('Delayed MAX message cancel requested: method=%s', method)
    return {'chat_id': chat_id, 'id': message_id, 'cancelled': method is not None, 'method': method}

async def start_rpc(path: Path, get_user, archive=None):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    try:
        current = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if not stat.S_ISSOCK(current.st_mode) or current.st_uid != os.getuid():
            raise RuntimeError('Refusing to replace non-socket or foreign socket')
        path.unlink()
    lock = asyncio.Semaphore(2)
    opening_lock = asyncio.Lock()
    indexing_lock = asyncio.Lock()
    delayed_lock = asyncio.Lock()
    async def handle(request):
        user = get_user()
        if user is None:
            return web.json_response({'error':'MAX owner is not available'}, status=503)
        try:
            q = request.query.get('q','')
            if request.path.startswith('/archive/'):
                if archive is None: return web.json_response({'error':'archive unavailable'},status=503)
                if request.path == '/archive/messages':
                    result=await archive.search_messages(user.mxid,q,request.query.get('chat'),int(request.query.get('limit','100')),int(request.query.get('offset','0')))
                elif request.path == '/archive/contacts':result=await archive.search_directory(user.mxid,q,'contact')
                elif request.path == '/archive/chats':result=await archive.search_directory(user.mxid,q,'chat')
                else:result=await archive.status(user.mxid)
                return web.json_response(result)
            if user.max_client is None or not user.max_client.is_ready:
                return web.json_response({'error':'MAX session is not connected'}, status=503)
            client = user.max_client.client
            async with lock:
                if request.path == '/directory/refresh':
                    fetched=await asyncio.wait_for(client.fetch_chats(),timeout=30)
                    saved=await archive.save_directory(user.mxid,client) if archive else 0
                    result={'fetched':len(fetched or []),'indexed_directory':saved,'partial':True}
                elif request.path == '/index/chats':
                    limit=int(request.query.get('limit','50'))
                    offset=int(request.query.get('offset','0'))
                    if not 1<=limit<=100 or not 0<=offset<=10000:raise ValueError('invalid pagination')
                    chats=client.chats or []
                    has_more=len(chats)>offset+limit
                    result={'chats':[{'id':chat.id,'title':chat.title,'type':str(chat.type)} for chat in chats[offset:offset+limit]],
                            'partial':True,'has_more':has_more,'next_offset':offset+limit if has_more else None}
                elif request.path == '/attachment':
                    chat=int(request.query['chat']);message_id=int(request.query['message']);index=int(request.query.get('index','0'))
                    message=await client.get_message(chat,message_id)
                    if message is None or not 0 <= index < len(message.attaches or []):
                        raise ValueError('attachment does not exist')
                    media=await user.max_client.download_attachment(message,message.attaches[index],max_size=50*1024*1024)
                    if media is None: raise ValueError('unsupported attachment')
                    return web.Response(body=media.data,content_type='application/octet-stream',headers={'Cache-Control':'no-store'})
                elif request.path == '/delayed/send':
                    async with delayed_lock: result=await send_delayed(user,request)
                elif request.path == '/delayed':
                    result=await list_delayed(client,int(request.query['chat']))
                elif request.path == '/delayed/cancel':
                    async with delayed_lock: result=await cancel_delayed(client,int(request.query['chat']),int(request.query['message']))
                elif request.path == '/open-contact':
                    async with opening_lock: result=await open_contact(user,int(request.query['id']))
                elif request.path == '/open-chat':
                    async with opening_lock: result=await user.sync_group_portal_by_chat_id(str(int(request.query['id'])))
                elif request.path == '/index':
                    if archive is None: return web.json_response({'error':'archive unavailable'},status=503)
                    chat=int(request.query['chat']);pages=int(request.query.get('pages','1'))
                    async with indexing_lock:
                        checkpoint=await archive.get_checkpoint(user.mxid,chat)
                        if request.query.get('fresh') == '1' and 'before' in request.query:raise ValueError('fresh conflicts with before')
                        before=(None if request.query.get('fresh') == '1' else
                            int(request.query['before']) if 'before' in request.query else (checkpoint or {}).get('next_before_ms'))
                        result=await read_history(client,chat,pages,before,archive=archive,owner=user.mxid)
                        await archive.save_checkpoint(user.mxid,chat,result['next_before_ms'],result['pages_fetched'],result['scanned'])
                    result.pop('messages',None)
                elif request.path == '/contacts': result=search_contacts(client,q)
                elif request.path == '/chats': result=search_chats(client,q)
                else:
                    chat=int(request.query['chat']); pages=int(request.query.get('pages','1'))
                    before=int(request.query['before']) if 'before' in request.query else None
                    if request.query.get('read') == '1' or request.path == '/index': result=await read_history(client,chat,pages,before,archive=archive,owner=user.mxid if archive else None)
                    else: result=await search_history(client,chat,q,pages,before,archive=archive,owner=user.mxid if archive else None)
                    if request.path == '/index':result.pop('messages',None)
            return web.json_response(result)
        except DelayedError as exc:
            return web.json_response({'error':str(exc)},status=400)
        except (KeyError, TypeError, ValueError):
            return web.json_response({'error':'invalid search parameters'},status=400)
        except Exception as exc:
            # Provider errors may include private content or tokens.
            log.warning('Local MAX operation failed: %s',type(exc).__name__)
            return web.json_response({'error':'MAX operation failed or is unavailable'},status=503)
    app=web.Application(client_max_size=1024)
    app.add_routes([web.get('/contacts',handle),web.get('/chats',handle),web.get('/history',handle),web.get('/attachment',handle),web.post('/open-contact',handle),web.post('/open-chat',handle),web.post('/index',handle),web.get('/index/chats',handle),web.post('/directory/refresh',handle),web.get('/archive/messages',handle),web.get('/archive/contacts',handle),web.get('/archive/chats',handle),web.get('/archive/status',handle),web.post('/delayed/send',handle),web.get('/delayed',handle),web.post('/delayed/cancel',handle)])
    runner=web.AppRunner(app,access_log=None)
    await runner.setup()
    try:
        await web.UnixSite(runner,path=str(path)).start()
        os.chmod(path,0o600)
    except BaseException:
        await runner.cleanup()
        raise
    return runner
