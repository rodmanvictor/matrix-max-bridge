"""Safely publish a completed MAX WEB session for the bridge to adopt."""
from __future__ import annotations
import os
from pathlib import Path

WEB_SESSION_MARKER = '__web_qr__'

def commit_session(stage: Path, final: Path, marker: Path) -> None:
    stage, final, marker = Path(stage), Path(final), Path(marker)
    if not (stage / 'session.db').is_file():
        raise ValueError('An authenticated session is required')
    final.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if final.exists() or marker.exists():
        raise FileExistsError('An existing session must not be replaced')
    lock=final.parent / ('.' + final.name + '.lock')
    fd=os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    moved=False
    try:
        if final.exists() or marker.exists():
            raise FileExistsError('An existing session must not be replaced')
        stage.rename(final);moved=True
        with marker.open('x', encoding='utf-8') as out:out.write('ready\n')
        marker.chmod(0o600)
    except BaseException:
        if moved and not stage.exists() and final.exists():final.rename(stage)
        raise
    finally:
        lock.unlink(missing_ok=True)
