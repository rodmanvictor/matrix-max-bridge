"""Safely publish a completed MAX WEB session for the bridge to adopt."""
from __future__ import annotations
import os
from pathlib import Path

WEB_SESSION_MARKER = '__web_qr__'

# `!max logout` deletes the session but keeps the stable device profile of an
# older phone login. A directory holding nothing else is free for a new login.
KEPT_AFTER_LOGOUT = frozenset({'device-profile.json'})


def is_logged_out(final: Path) -> bool:
    """True when a session directory only holds what `!max logout` leaves behind."""
    final = Path(final)
    if final.is_symlink() or not final.is_dir():
        return False
    return all(
        child.name in KEPT_AFTER_LOGOUT and child.is_file() and not child.is_symlink()
        for child in final.iterdir()
    )


def session_in_use(final: Path, marker: Path) -> bool:
    """True when a new login must not replace what is already there."""
    final, marker = Path(final), Path(marker)
    if marker.exists() or marker.is_symlink():
        return True
    return (final.exists() or final.is_symlink()) and not is_logged_out(final)


def commit_session(stage: Path, final: Path, marker: Path) -> None:
    stage, final, marker = Path(stage), Path(final), Path(marker)
    if not (stage / 'session.db').is_file():
        raise ValueError('An authenticated session is required')
    final.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    marker.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if session_in_use(final, marker):
        raise FileExistsError('An existing session must not be replaced')
    lock=final.parent / ('.' + final.name + '.lock')
    fd=os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    moved=False
    kept: list[tuple[Path, Path]] = []
    try:
        if session_in_use(final, marker):
            raise FileExistsError('An existing session must not be replaced')
        if final.exists():
            # Carry the kept device profile over into the new session directory.
            for child in list(final.iterdir()):
                target = stage / child.name
                if target.exists():
                    raise FileExistsError('The new session already contains ' + child.name)
                child.rename(target);kept.append((target, child))
            final.rmdir()
        stage.rename(final);moved=True
        with marker.open('x', encoding='utf-8') as out:out.write('ready\n')
        marker.chmod(0o600)
    except BaseException:
        if moved and not stage.exists() and final.exists():final.rename(stage)
        if kept:
            final.mkdir(mode=0o700, exist_ok=True)
            for current, original in kept:
                if current.exists() and not original.exists():current.rename(original)
        raise
    finally:
        lock.unlink(missing_ok=True)
