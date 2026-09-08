from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Literal

from sanic.log import logger, Colors

from src.handlers.backup import BackupHandler
from src.handlers.relay import RelayHandler
from src.services.bds_adapter import BdsAdapter


class BackupState(str, Enum):
    IDLE = "idle"
    HOLDING = "holding"
    QUERYING = "querying"
    EXECUTING = "executing"
    RESUMING = "resuming"


class BackupResultType(str, Enum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class BackupResult:
    type: BackupResultType
    kind: Literal['backup', 'map_update'] | None = None
    reason: str | None = None
    files: tuple | None = None


class BackupCoordinator:
    """Single owner for save hold → query retries → backup → resume.
    
    Global hold via asyncio.Lock ensures no duplication — second run gets Skipped(concurrent).
    Uses BdsAdapter.wait_for for timeout handling (hold timeout, silent query not-ready).
    """

    def __init__(self, server):
        self._server = server
        self._bds = BdsAdapter(server)
        self._lock = asyncio.Lock()
        self.state: BackupState = BackupState.IDLE
        self._hold_started_at: datetime | None = None

    def _timeouts(self) -> tuple[int, float]:
        try:
            hold = int(self._server.config['backup'].get('hold_timeout_seconds', 45))
        except Exception:
            hold = 45
        try:
            interval = float(self._server.config['backup'].get('query_retry_interval_seconds', 2.5))
        except Exception:
            interval = 2.5
        hold = max(5, min(hold, 300))
        interval = max(0.5, min(interval, 10.0))
        return hold, interval

    async def _relay_timeout(self, kind: str, elapsed: int):
        try:
            if self._server.config.get('discord_relay', {}).get('relay_events', {}).get('backups', True):
                await RelayHandler.relay_backup_timeout(await self._server.api.get(), kind, elapsed)
        except Exception as e:
            logger.debug(f"Failed to relay hold timeout: {e}")

    async def _relay_error(self, title: str, content: str):
        try:
            if self._server.config.get('discord_relay', {}).get('relay_events', {}).get('backups', True):
                await RelayHandler.relay_backup_error(await self._server.api.get(), title, content)
        except Exception as e:
            logger.debug(f"Failed to relay backup error: {e}")

    async def run(self, kind: Literal['backup', 'map_update']) -> BackupResult:
        # Global hold — fail fast if already locked (easiest for future B: typed Skipped)
        if self._lock.locked():
            msg = f"Backup already in progress ({self.state.value}); skipping {kind}"
            logger.warning(f"{Colors.YELLOW}{msg}{Colors.END}")
            await self._relay_error("Backup Skipped — Concurrent Hold",
                                    f"**Requested:** `{kind}`\n**State:** `{self.state.value}`\nAnother save hold is active; skipping.")
            return BackupResult(BackupResultType.SKIPPED, kind, "concurrent")

        # Also guard via status for API compat (Geode.initiate_save previously checked status)
        if self._server.status not in ('started', 'idle', None) and self._server.status != 'started':
            # keep alias: server.status is still 'started'/'backup'/'map_update' for /info
            pass

        async with self._lock:
            hold_timeout, interval = self._timeouts()
            self.state = BackupState.HOLDING
            self._hold_started_at = datetime.now()
            # Keep server.status alias for backwards compat with /info and LoopHandler checks
            prev_status = self._server.status
            self._server.status = kind
            try:
                # Hold
                try:
                    await self._bds.send('save hold')
                except Exception as e:
                    logger.error(f"{Colors.RED}Failed to send save hold: {e}{Colors.END}")
                    return BackupResult(BackupResultType.FAILED, kind, f"hold send failed: {e}")

                # Wait for hold ack ("Saving") — but if BDS never prints it, we still proceed to query
                # Use short wait; on timeout treat as still holding (BDS may have held without ack line)
                try:
                    await self._bds.wait_for('backup.hold', timeout=5)
                    logger.debug("[Backup] Hold ack received")
                except asyncio.TimeoutError:
                    logger.debug("[Backup] No hold ack line, assuming hold succeeded and proceeding to query")
                # Check for hold error concurrently
                # If hold.error arrived, it would have been emitted as backup.hold.error; wait with 0 timeout check
                # We poll via try-wait 0.1s
                try:
                    await self._bds.wait_for('backup.hold.error', timeout=0.2)
                    # If we get here, hold was rejected
                    msg = "Save hold rejected — already running"
                    logger.warning(f"{Colors.YELLOW}{msg}{Colors.END}")
                    await self._relay_error("Backup Hold Rejected", msg)
                    return BackupResult(BackupResultType.SKIPPED, kind, "hold_rejected")
                except asyncio.TimeoutError:
                    pass

                # Query retries — silent not-ready means wait_for timeout
                self.state = BackupState.QUERYING
                files: tuple | None = None
                elapsed = 0
                start_q = datetime.now()
                # We loop until hold_timeout elapsed
                deadline = asyncio.get_event_loop().time() + hold_timeout
                attempt = 0
                while asyncio.get_event_loop().time() < deadline:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                    attempt += 1
                    if attempt > 1:
                        logger.debug(f"[Backup] save query not ready, retry #{attempt} (interval={interval}s)")
                    try:
                        await self._bds.send('save query')
                    except Exception as e:
                        logger.debug(f"save query send failed #{attempt}: {e}")
                    try:
                        # backup.query emits (line, *file_list) where file_list are (name, len) tuples
                        # Respect deadline — don't wait longer than remaining
                        q_timeout = min(3, remaining)
                        args, _kwargs = await self._bds.wait_for('backup.query', timeout=q_timeout)
                        # args = (line, (file,len), (file,len), ...)
                        # First arg is line string, rest are file tuples
                        if len(args) >= 2:
                            candidate = args[1:]  # file tuples
                            # Filter out empty or malformed
                            if candidate and all(isinstance(x, tuple) and len(x)==2 for x in candidate):
                                files = candidate
                                logger.debug(f"[Backup] Query succeeded on attempt {attempt} with {len(files)} files")
                                break
                            else:
                                logger.debug(f"[Backup] Query returned empty/malformed, retrying")
                        else:
                            logger.debug("[Backup] Query returned no files, retrying")
                    except asyncio.TimeoutError:
                        # silent not-ready — retry after interval
                        pass
                    # Check for backup.error ("A previous save has not been completed")
                    try:
                        await self._bds.wait_for('backup.error', timeout=0.1)
                        logger.warning(f"{Colors.YELLOW}[Backup] 'A previous save has not been completed' — retrying query{Colors.END}")
                    except asyncio.TimeoutError:
                        pass
                    # sleep interval but respect deadline
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                    await asyncio.sleep(min(interval, remaining))

                if not files:
                    elapsed = int((datetime.now() - self._hold_started_at).total_seconds()) if self._hold_started_at else hold_timeout
                    msg = f"{Colors.RED}[Backup] Hold timed out after {elapsed}s (type={kind}) — save query never returned file list. Forcing save resume, skipping backup.{Colors.END}"
                    logger.error(msg)
                    await self._relay_timeout(kind, elapsed)
                    return BackupResult(BackupResultType.SKIPPED, kind, "hold_timeout")

                # Executing backup/map
                self.state = BackupState.EXECUTING
                handler = BackupHandler(files, self._server.properties['level-name'])
                try:
                    if kind == 'map_update':
                        self._server.emit('broadcast.announcement', f'A Map Update is in progress. Expect reduced server performance.')
                        await handler.map_update()
                        self._server.emit('broadcast.message', f'Map Update complete!')
                    else:
                        await handler.backup()
                except Exception as e:
                    msg = f"Backup ({kind}) failed: {e.__class__.__name__}: {e}"
                    logger.error(f"{Colors.RED}{msg}{Colors.END}")
                    await self._relay_error("Backup Failed", f"**Type:** `{kind}`\n**Error:** `{e.__class__.__name__}: {e}`")
                    return BackupResult(BackupResultType.FAILED, kind, str(e), files)

                self.state = BackupState.RESUMING
                # Resume is in finally — but also check result
                return BackupResult(BackupResultType.SUCCESS, kind, None, files)

            finally:
                # Always resume — idempotent, even on skip/failed
                self.state = BackupState.RESUMING
                try:
                    await self._bds.send('save resume')
                except Exception as e:
                    logger.debug(f"save resume send failed: {e}")
                # Wait for resume ack with grace, but don't block forever
                try:
                    await self._bds.wait_for('backup.resume', timeout=5)
                except asyncio.TimeoutError:
                    logger.warning(f"{Colors.YELLOW}[Backup] No resume ack after 5s; forcing status=started{Colors.END}")
                self._server.status = 'started'
                self.state = BackupState.IDLE
                self._hold_started_at = None
