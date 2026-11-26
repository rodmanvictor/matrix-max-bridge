"""Account-scoped search archive. Never store credentials or signed file URLs."""
from __future__ import annotations
import json
import time


def _query(value: str) -> str:
    term = str(value).strip().casefold()
    if not term or len(term) > 256:
        raise ValueError('query must contain 1..256 characters')
    # LIKE metacharacters are treated as literal user input.
    term = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return '%' + term + '%'


def _message_values(owner, chat_id, message):
    files = [{'index':i,'name':a.name} for i,a in enumerate(getattr(message, 'attaches', None) or [])
             if isinstance(getattr(a, 'name', None), str)]
    text = str(getattr(message,'text',None) or '')
    filename_text = ' '.join(item['name'] for item in files)
    sender = getattr(message,'sender',None)
    return (str(owner),str(chat_id),str(message.id),int(message.time or 0),
            str(sender) if sender is not None else None,text,
            json.dumps(files,ensure_ascii=False), (text+' '+filename_text).casefold())


class Archive:
    def __init__(self, db): self.db = db

    async def save_message(self, owner, chat_id, message):
        await self.save_messages(owner,chat_id,[message])

    async def save_messages(self, owner, chat_id, messages):
        rows = [_message_values(owner,chat_id,m) for m in messages if getattr(m,'id',None) is not None]
        if not rows: return 0
        await self.db.executemany('''INSERT INTO max_archive_message
            (owner,chat_id,message_id,timestamp_ms,sender_id,body,files_json,search_text)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (owner,chat_id,message_id) DO UPDATE SET
            timestamp_ms=excluded.timestamp_ms,sender_id=excluded.sender_id,
            body=excluded.body,files_json=excluded.files_json,search_text=excluded.search_text''',rows)
        return len(rows)

    async def save_directory(self, owner, client):
        rows=[]; now=int(time.time()*1000)
        own_id=getattr(getattr(getattr(client,'me',None),'contact',None),'id',None)
        for contact in client.contacts or []:
            if contact is None: continue
            names=[]
            for name in contact.names:
                names.extend(x for x in (name.name,name.first_name,name.last_name,
                    ' '.join(x for x in (name.first_name,name.last_name) if x)) if x)
            names=list(dict.fromkeys(names))
            chat_id=client.get_chat_id(int(own_id),int(contact.id)) if own_id is not None else None
            rows.append((str(owner),'contact',str(contact.id),str(chat_id) if chat_id is not None else None,
                json.dumps(names,ensure_ascii=False),' '.join(names).casefold(),now))
        for chat in client.chats or []:
            name=getattr(chat,'title',None)
            if not name: continue
            rows.append((str(owner),'chat',str(chat.id),str(chat.id),json.dumps([name],ensure_ascii=False),str(name).casefold(),now))
        if rows:
            await self.db.executemany('''INSERT INTO max_archive_directory
                (owner,kind,remote_id,chat_id,names_json,search_text,observed_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7)
                ON CONFLICT (owner,kind,remote_id) DO UPDATE SET chat_id=excluded.chat_id,
                names_json=excluded.names_json,search_text=excluded.search_text,observed_at=excluded.observed_at''',rows)
        return len(rows)

    async def search_messages(self, owner, query, chat_id=None, limit=100, offset=0):
        if not 1<=limit<=100 or not 0<=offset<=10000: raise ValueError('invalid pagination')
        rows=await self.db.fetch('''SELECT chat_id,message_id,timestamp_ms,sender_id,body,files_json
            FROM max_archive_message WHERE owner=$1 AND search_text LIKE $2 ESCAPE '\\'
            AND (CAST($3 AS TEXT) IS NULL OR chat_id=$3) ORDER BY timestamp_ms DESC,chat_id,message_id
            LIMIT $4 OFFSET $5''',str(owner),_query(query),str(chat_id) if chat_id is not None else None,limit+1,offset)
        messages=[{'chat_id':r['chat_id'],'id':r['message_id'],'time':r['timestamp_ms'],
            'sender':r['sender_id'],'text':r['body'],'files':json.loads(r['files_json'])} for r in rows[:limit]]
        return {'messages':messages,'partial':True,'has_more':len(rows)>limit,
                'scope':'locally indexed MAX messages; remote history may be incomplete'}

    async def search_directory(self, owner, query, kind, limit=100):
        if kind not in ('contact','chat') or not 1<=limit<=100:raise ValueError('invalid directory search')
        rows=await self.db.fetch('''SELECT remote_id,chat_id,names_json,observed_at
            FROM max_archive_directory WHERE owner=$1 AND kind=$2 AND search_text LIKE $3 ESCAPE '\\'
            ORDER BY observed_at DESC,remote_id LIMIT $4''',str(owner),kind,_query(query),limit+1)
        return {'matches':[{'id':r['remote_id'],'chat_id':r['chat_id'],
                 'names':json.loads(r['names_json']),'observed_at':r['observed_at']} for r in rows[:limit]],
                'partial':True,'has_more':len(rows)>limit,'scope':'locally indexed MAX directory'}

    async def status(self, owner):
        row=await self.db.fetchrow("SELECT COUNT(*) AS count, COUNT(DISTINCT chat_id) AS chats FROM max_archive_message WHERE owner=$1",str(owner))
        dirs=await self.db.fetch("SELECT kind,COUNT(*) AS count FROM max_archive_directory WHERE owner=$1 GROUP BY kind",str(owner))
        return {'messages':row['count'],'indexed_chats':row['chats'],'directory':{r['kind']:r['count'] for r in dirs},'partial':True,
                'scope':'local archive; not all remote history is necessarily indexed'}

    async def get_checkpoint(self, owner, chat_id):
        row=await self.db.fetchrow('''SELECT next_before_ms,pages,scanned,updated_at
            FROM max_archive_checkpoint WHERE owner=$1 AND chat_id=$2''',str(owner),str(chat_id))
        if row is None:return None
        return {'next_before_ms':row['next_before_ms'],'pages':row['pages'],
                'scanned':row['scanned'],'updated_at':row['updated_at'],'partial':True}

    async def save_checkpoint(self, owner, chat_id, next_before_ms, pages, scanned):
        await self.db.execute('''INSERT INTO max_archive_checkpoint
            (owner,chat_id,next_before_ms,pages,scanned,updated_at) VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT (owner,chat_id) DO UPDATE SET
            next_before_ms=CASE
                WHEN max_archive_checkpoint.next_before_ms IS NULL THEN excluded.next_before_ms
                WHEN excluded.next_before_ms IS NULL THEN max_archive_checkpoint.next_before_ms
                WHEN excluded.next_before_ms < max_archive_checkpoint.next_before_ms THEN excluded.next_before_ms
                ELSE max_archive_checkpoint.next_before_ms END,
            pages=max_archive_checkpoint.pages+excluded.pages,
            scanned=max_archive_checkpoint.scanned+excluded.scanned,updated_at=excluded.updated_at''',
            str(owner),str(chat_id),next_before_ms,pages,scanned,int(time.time()*1000))
