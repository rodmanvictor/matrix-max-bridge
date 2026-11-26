# API and CLI

## Matrix API: Telegram and MAX

When a message has been bridged into a Matrix room, use the same Matrix
Client-Server API regardless of its origin. For example, `matrix-agent --owner
search 'текст'` calls `POST /_matrix/client/v3/search`. The owner must be a
member of the room. Synapse cannot search end-to-end encrypted message bodies;
the local CLI does not decrypt such messages. A Matrix event ID returned by
`send` or `send-file` means Synapse accepted the event, not that MAX or Telegram
has delivered it.

`tools/matrix-agent` supports `status`, `rooms`, `join`, `history`, `search`,
`send`, `send-file`, and `download`. It returns JSON. `MATRIX_HOMESERVER`
(default `http://127.0.0.1:8008`) and `MATRIX_TOKEN_FILE` (default
`~/.config/matrix-agent/token`) select an installation and account. `--owner`
switches to the token in `MATRIX_OWNER_TOKEN_FILE` (default
`~/.config/matrix-agent/owner_token`), for example a separate device of your own
account with access to all your rooms. Keep token files mode 0600.

## Local MAX API

The bridge can expose an HTTP API over a Unix domain socket only. Set
`MAX_RPC_MXID` to the permitted owner Matrix ID and `MAX_RPC_SOCKET` to the
socket path inside the bridge; the default is `/data/run/max.sock`. With the
Docker layout from the README use `/opt/mautrix-max/data/run/max.sock`. Limit
filesystem access to the owner and bridge process. There is no network listener
for this API. The accompanying CLI `tools/matrix-max` accepts
`MATRIX_MAX_SOCKET` (default `/data/run/max.sock`); `open-contact` and
`open-chat` also call `matrix-agent --owner join`, so both tools must be on
`PATH`. Run `tools/matrix-max --help` for all commands.

- `GET /archive/status`: number of indexed messages, chats and directory items.
- `GET /archive/messages?q=...&chat=...&limit=...&offset=...`: bounded,
  account-scoped substring search of saved message text and file names. `chat`
  is optional. Limits are 1..100, offset is 0..10000.
- `GET /archive/contacts?q=...`, `GET /archive/chats?q=...`: search saved
  contact/chat names; results can contain several people with similar names.
- `GET /contacts?q=...`, `GET /chats?q=...`: search the currently connected
  MAX session's cached contacts/chats.
- `GET /history?chat=...&read=1&pages=...`: fetch bounded MAX history for one
  explicitly selected chat; fetched messages are also stored in the archive.
  With a `q` parameter and no `read=1`, search the fetched page instead.
- `GET /attachment?chat=...&message=...&index=...`: fetch a supported MAX
  attachment, at most 50 MiB, by explicit message ID and attachment index.
- `POST /index?chat=...&pages=...`: fetch 1..5 pages for a selected chat and
  save the checkpoint. `fresh=1` checks recent messages without advancing an
  older saved checkpoint; `before` can specify an explicit timestamp.
- `POST /directory/refresh`: explicitly refresh the currently cached chat list.
- `POST /open-contact?id=...`, `POST /open-chat?id=...`: create or find a
  local Matrix room for a selected known contact/chat. These endpoints do not
  send a MAX message. The CLI also joins the room as the local Matrix owner.
- `POST /delayed/send?chat=...&at=UNIX_SECONDS&kind=text`: schedule a native
  MAX delayed message; the request body is the UTF-8 text, at most 16 KiB.
  With `kind=image|video|file&name=FILENAME` the body is the raw attachment,
  at most 50 MiB, sent without text. `at` must be 60 seconds to 366 days ahead.
  MAX stores the message and sends it itself: it is listed among the chat's
  delayed messages in the MAX apps and does not depend on this bridge at send time.
- `GET /delayed?chat=...`: delayed messages of one chat (at most 100) with
  `time_to_fire_ms`.
- `POST /delayed/cancel?chat=...&message=...`: delete one message that is still
  in the delayed list; `cancelled` reports whether it left the list.

The bridge does **not** automatically load historical conversations on start.
The archive receives new events and explicitly requested history. All MAX
history/directory searches report `partial`: the MAX chat cache or history may
be incomplete and a timestamp page boundary may omit messages. Archive results
are a supplementary local database, not a Matrix history import. Message
edits/deletions may not be reflected reliably. No credentials, signed file URLs,
or session tokens are stored in archive rows.

## Notes

Anyone who can open the socket can read the archive and send messages as the
owner. Keep it mode 0600 and do not expose it to other containers.

The archive stores message text, names and file names in the bridge database.
Restrict access to the database and its backups. Messages may remain in the
archive after they are deleted in MAX; there is no retention policy yet.

Delayed messages, as observed against MAX on 2026-11-26:

- MAX fires delayed messages on the whole minute, so schedule consecutive
  messages on different minutes;
- a direct chat lists its delayed messages for a backward request from a
  far-future point, a group chat only for a forward request from now;
- a plain `MSG_DELETE` leaves a delayed message in place, `itemType: DELAYED`
  removes it. PyMax has no API for that delete, so `cancel_delayed` sends the
  opcode directly.

Test new behaviour in your own saved-messages chat (chat ID `0`) before using
it in other chats.
