# Option B Plan — Full BDS Command-Response Bus Replacement

> **For future Muse Spark session — self-contained.**
> You are reading this without prior context. This doc captures everything needed to implement Option B.
> Mode: `plan` was active when authored; `build` now allows edits. Base branch for Option A is `fix/backup-coordinator-a` off `develop` (commit `33a7dba`). Do NOT re-apply `fix/backup-hold-timeout` (commit `3a37345`) — it was discarded for duplicating backups.

---

## 0. Quick Resume Instructions

If you are a new session:

1. `git branch --show-current` should be `fix/backup-coordinator-a` (Option A). If not: `git checkout fix/backup-coordinator-a` or `git checkout develop && git checkout -b fix/backup-coordinator-b-from-a`.
2. `git status` should show modified `config.default.yml`, `src/geode.py`, `src/handlers/relay.py`, `src/server.py` + untracked `src/services/bds_adapter.py`, `src/services/backup_coordinator.py` (Option A). Verify with `uv run --python 3.12 python -m py_compile src/server.py src/geode.py src/services/backup_coordinator.py`.
3. This plan (Option B) builds ON TOP of Option A — do not revert Option A.
4. Read §1-§3 for background, then jump to §6 Implementation Steps.

---

## 1. Background & Why Option B Exists

### 1.1 Original Bug

Flow intended:

```
Save hold → "Saving" → Save query → list of files → copy → Save resume
```

Reality: `save query` does NOT guarantee filenames immediately or ever. Sometimes silence (no line). Original code in `src/server.py:288` did:

```python
@events.on('backup.hold')
async def on_backup_hold(self, line: str):
    await self.send_command('save query')  # single fire
```

And `src/server.py:292` `on_backup_query` was the ONLY place that did `save resume`. If query never returned, `status` stuck `backup|map_update`, BDS held save data forever → infinite growth. No timeout, no retry.

### 1.2 Option A (Current, Shipped on `fix/backup-coordinator-a`)

- Added `config.default.yml:27` `hold_timeout_seconds:45` + `query_retry_interval_seconds:2.5`
- Added `src/handlers/relay.py:73` `relay_backup_timeout` / `relay_backup_error` (console `logger.error` + Discord)
- Created `src/services/bds_adapter.py` (thin `BdsAdapter(server)` with `send`/`wait_for`/`execute`)
- Created `src/services/backup_coordinator.py` — single owner `BackupCoordinator(server)`:
  - `hold_lock: asyncio.Lock` global hold (no duplicate)
  - `state: BackupState` enum, alias `server.status` for `/info`
  - `run(kind)` → `send save hold` → `wait_for('backup.hold',5)` → `wait_for('backup.hold.error',0.2)` → loop `send save query` → `wait_for('backup.query', min(3, remaining))` until `hold_timeout` deadline → skip+resume+relay on timeout → `BackupHandler` `src/handlers/backup.py:186` → `finally` `send save resume` + `wait_for('backup.resume',5)` grace
  - Server `src/server.py:40` got `_waiters: dict[str, list[Future]]` + `wait_for(event, timeout)` + `emit` fulfills waiters; old `on_backup_hold`/`on_backup_query`/`on_backup_error` removed, kept only idempotent `on_backup_resume`
  - `src/geode.py:51` `initiate_save` now `await coordinator.run(kind)`; concurrent second run returns `Skipped(concurrent)` and raises `Exception` for API compat

**Option A fix for duplication bug in prior `fix/backup-hold-timeout`:** Prior fix had two pollers (`_poller_task` + `_fallback_task`) + `status` string race → 2 concurrent `BackupHandler` runs. Option A fixes by ONE coordinator lock + ONE poll loop.

**Option A leaves:** `pyventus` `EventLinker`/`AsyncIOEventEmitter` `src/server.py:24,33,36`, `parsers[]` O(n) scan `src/server.py:52-72`, `EventParser` regex list, `LoopHandler` `src/handlers/loop.py:15` `while sleep`, `ConfigHandler(UserDict)` `src/handlers/config.py:5`.

### 1.3 Why Option A Is Not Long-Term

Events are great for fan-out (`player.connect` → relay, `broadcast.message` → tellraw) but **terrible for request-response** (`save hold → query → resume` needs correlation, timeout, retry, cancel). Option A papers this with `wait_for` adapter over `emit`, but still:

- O(n) parser per stdout line (`for event in parsers: regex.search` `src/server.py:98`)
- Class-var `__event_emitter` shared across instances, `EventLinker` decorator magic hard to mock
- Global mutable `status` string, no typed state, no backpressure (`emit` fires even if handler busy)
- `LoopHandler` `while sleep` swallow `CancelledError` as `logger.exception` `src/handlers/loop.py:60`, no jitter, no `TaskGroup`
- Adding new BDS commands (e.g., `whitelist list`, `gamerule`) means new `EventParser` + new `status` value + new watchdog variant

If Geode stays “hourly backup + map render” `README.md:21`, Option A is enough. If Geode will handle more sequential BDS commands, Option B pays off.

---

## 2. Option B Goal

Replace the entire `pyventus` bus for BDS interaction with a **typed, queue-based command-response bus**:

- `BdsClient` owns subprocess I/O, parses lines via **O(1) dict dispatch**, pushes typed `BdsEvent` into `asyncio.Queue(maxsize=1024)` (backpressure)
- Callers do `await bds.execute('save hold', HOLD_ACK, timeout=5)` → `Future` → no poller/watchdog tasks, timeout is the `wait_for`
- Adding a command = one line, not new parser+status+handler
- Tests use `FakeBdsClient(responses=[...])` without subprocess, no `patch('src.server.BackupHandler')`

---

## 3. Option A vs B Comparison

| Dimension | A (current) | B | Long-term impact |
|---|---|---|---|
| Correctness | Hold needs poller+watchdog+fallback+status string; 3 tasks to cancel `src/server.py:226` | `execute` with `wait_for` is the watchdog — one `Future` | B eliminates stuck-hold class |
| Dispatch cost | O(n)=7 regex/search per line | O(1) dict on first token + 1 regex for that type | B matters at 100s lines/sec during map render `src/handlers/backup.py:144` |
| Testability | `patch` + `emit('backup.hold')` + class-var emitter leak | `FakeBdsClient([HOLD_ACK, QUERY_RESULT])` <50ms | B enables unit tests without Docker |
| Coupling | `BedrockServer` imports `BackupHandler`, `RelayHandler`, `ConfigHandler`, `ManagedAPIClient` | `BdsClient` only I/O; `BackupCoordinator` only hold/query; `Relay` only notify; `Scheduler` only timing | B = SRP, smaller PRs |
| Observability | `logger.info(line)` vs `logger.info(YELLOW+line)` `src/server.py:114` | `BdsResponse` typed → `metrics.counter('bds.hold.ack')` | B needed for `backup.skipped` alerts |
| Backpressure | `emit` fires even if handler busy; `LoopHandler` `del` swallows cancel | `Queue(maxsize)` blocks reader; `TaskGroup` cancels coordinator → `finally` resumes | B prevents blow-up during `unmined` render |
| Dependency | `pyventus==0.7.1` magic decorator | stdlib `asyncio.Queue`+`Future` | B reduces supply-chain risk |

---

## 4. Option B Detailed Architecture

### 4.1 File Tree (End State)

```
src/services/bds_client.py          # NEW, replaces pyventus for BDS
src/services/bds_types.py           # NEW, enums + dataclasses
src/services/backup_coordinator.py  # EXISTS (Option A) — update to use BdsClient
src/services/bds_adapter.py         # DELETE or keep as alias to BdsClient
src/services/scheduler.py           # NEW, replaces LoopHandler
src/server.py                       # STRIP: parsers→dict, emit→queue, handlers→subscribers
src/geode.py                        # slim: owns BdsClient + coordinator + scheduler
config.default.yml                  # + BackupConfig pydantic validation (optional)
src/handlers/relay.py               # unchanged from Option A
```

### 4.2 BdsClient Interface (Stable for Migration)

```python
# src/services/bds_types.py
class BdsEventType(Enum):
    PLAYER_CONNECT = auto()  # was parser 'player.connect' src/server.py:54
    PLAYER_SPAWN = auto()
    PLAYER_DISCONNECT = auto()
    SERVER_START = auto()    # '^Server started' src/server.py:59
    SERVER_STOP = auto()
    SERVER_CRASH = auto()
    HOLD_ACK = auto()        # 'Saving' src/server.py:67
    HOLD_ERROR = auto()      # 'The command is already running' src/server.py:68
    QUERY_RESULT = auto()    # findall r'(?:^|,\s*)([^:]+):(\d+)' src/server.py:69
    QUERY_ERROR = auto()     # 'A previous save has not been completed' src/server.py:70
    RESUME_ACK = auto()      # 'Changes to the world are resumed' src/server.py:71
    UNKNOWN = auto()

@dataclass
class BdsEvent:
    type: BdsEventType
    raw: str
    payload: dict  # e.g., {'gamertag': ..., 'xuid': ...} or {'files': [(name, len), ...]}
    line: str

# src/services/bds_client.py
class BdsClient:
    def __init__(self, proc: asyncio.subprocess.Process):
        self._proc = proc
        self._queue: asyncio.Queue[BdsEvent] = asyncio.Queue(maxsize=1024)
        self._pending: dict[tuple[str, int], Future] = {}  # (expect, id) -> future
        self._parsers: dict[str, Callable[[str], BdsEvent|None]]  # O(1) by prefix
        self._next_id = 0

    async def send(self, cmd: str, sleep: int = 0): ...

    async def execute(self, cmd: str, expect: BdsEventType, timeout: float) -> BdsEvent:
        # send + wait_for combined
        fut = get_loop().create_future()
        key = (expect, self._next_id); self._next_id+=1
        self._pending[key]=fut
        await self.send(cmd)
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(key, None)

    async def wait_for(self, expect: BdsEventType, timeout: float) -> BdsEvent:
        # wait without send (for hold ack that arrives without explicit execute)
        ...

    async def subscribe(self, *types: BdsEventType) -> AsyncIterator[BdsEvent]:
        # for fan-out: player connect → relay
        while True:
            ev = await self._queue.get()
            if ev.type in types: yield ev
            else: await self._queue.put(ev)  # or separate broadcast queue

    async def _reader_loop(self):
        while True:
            raw = (await self._proc.stdout.readline()).decode().rstrip()
            line = '] '.join(raw.split('] ')[1:]) if '] ' in raw else raw  # same as src/server.py:92
            ev = self._parse(line)  # O(1) dict lookup on first token, one regex for that type
            # fulfill pending futures first
            for (expect, _), fut in list(self._pending.items()):
                if expect == ev.type and not fut.done():
                    fut.set_result(ev); break
            else:
                # no pending, broadcast
                await self._queue.put(ev)
                # also log
                if ev.type == BdsEventType.UNKNOWN and line: logger.info(line)
```

**Parser dispatch:** Instead of `for event in parsers: if regex.search(line)` `src/server.py:98`, do:

```python
def _parse(self, line: str) -> BdsEvent:
    if line.startswith('Player connected:'): return parse_connect(line)  # regex only here
    if line.startswith('Saving'): return BdsEvent(HOLD_ACK, ...)
    if line.startswith('Changes to the world are resumed'): return BdsEvent(RESUME_ACK, ...)
    # ... etc, one if per type, then one regex for that type
    return BdsEvent(UNKNOWN, raw=line, payload={})
```

### 4.3 BackupCoordinator After B (Update Existing File)

`src/services/backup_coordinator.py` already exists in Option A. Change:

- `__init__(self, bds: BdsClient)` instead of `BdsAdapter(server)`
- `run` body stays same shape but uses `await self._bds.execute('save hold', HOLD_ACK, timeout=5)` etc., no manual `send`+`wait_for` for hold.error → use `asyncio.wait` on two futures.
- Remove `self._server.properties['level-name']` direct access → inject `level_name` via constructor (from `server.properties` once, or config)
- Remove `self._server.emit('broadcast.*')` → use `self._relay` or `self._event_bus` for map updates
- Keep `BackupState` enum, `hold_lock`, `_timeouts()` from `src/handlers/config.py`, relay calls `src/handlers/relay.py:73`

New `run` sketch (diff from Option A):

```python
# Before (A):
await self._bds.send('save hold')
try: await self._bds.wait_for('backup.hold', 5)
except TimeoutError: ...
try: await self._bds.wait_for('backup.hold.error', 0.2)

# After (B):
try:
    ev = await self._bds.execute('save hold', BdsEventType.HOLD_ACK, timeout=5)
except TimeoutError:
    # check if hold error was the reason
    ...
```

### 4.4 Scheduler (Replaces LoopHandler)

```python
# src/services/scheduler.py
@dataclass
class PeriodicTask:
    name: str
    interval: float
    jitter: float = 0.1
    coro: Callable
    retry_policy: RetryPolicy

class Scheduler:
    def __init__(self):
        self._tasks: list[asyncio.Task] = []

    def add(self, task: PeriodicTask):
        async def loop():
            await asyncio.sleep(task.jitter*random.random())
            while True:
                try:
                    await task.coro(geode)  # e.g., coordinator.run('backup')
                except asyncio.CancelledError: break
                except Exception as e:
                    logger.error(f"[{task.name}] {e}, retry in 30s"); await asyncio.sleep(30)  # was src/handlers/loop.py:60
                else:
                    await asyncio.sleep(task.interval)
        # started via TaskGroup in Geode.start()
```

`src/geode.py:75` `@looper.loop('Backup Loop', 3600, 60)` becomes `scheduler.add(PeriodicTask('Backup Loop', 3600, coro=backup_coro))`.

### 4.5 Server Slimming

`src/server.py` after B:

- Remove `from pyventus.events import EventLinker, AsyncIOEventEmitter` `src/server.py:24`
- Remove `__event_emitter`, `events: EventLinker`, `parsers: list[EventParser]` `src/server.py:33-36,52`
- Keep `__process`, `send_command`, `start`/`stop`/`kill`, `properties`, `online`, `version`
- `__server_output` now just `await self._bds_client._reader_loop()` or is moved into `BdsClient`
- Keep `on_player_*`/`on_server_*`/`on_broadcast_*` but as `async def handle_player_connect(self, ev: BdsEvent)` subscribed via `bds.subscribe(PLAYER_CONNECT)` in `Geode.__init__`, not decorator
- Backup parsers/handlers removed entirely (already removed in Option A `src/server.py:311`)

### 4.6 Geode Slimming

```python
class Geode:
    def __init__(self, server: BedrockServer = BedrockServer()):
        self.server = server
        self.bds = BdsClient(server._proc)  # or BdsClient factory
        self.backup_coordinator = BackupCoordinator(self.bds, level_name=server.properties['level-name'])
        self.scheduler = Scheduler()
        self.scheduler.add(PeriodicTask('Backup Loop', 3600, backup_coro))
```

---

## 5. Migration Ladder (No Big Bang)

```
A0 (done, fix/backup-coordinator-a): BdsAdapter.wait_for over emit, coordinator lock+timeout
A1 (current): Coordinator owns backup, LoopHandler still, parsers still
B1: Introduce BdsClient with Queue, keep BdsAdapter as alias → coordinator unchanged
B2: Switch coordinator to use BdsClient.execute directly, keep fallback wait_for for other events
B3: Move player/server/broadcast handlers to subscribe(BdsClient) — remove pyventus
B4: Replace LoopHandler with Scheduler TaskGroup
B5: ConfigHandler(UserDict) → pydantic BaseSettings (BackupConfig)
```

Each step is independently testable, no need to do all at once.

---

## 6. Implementation Steps (When You Resume Build Mode)

### Phase B1 — BdsClient Core (no behavior change)

1. Create `src/services/bds_types.py` with enums+dataclasses above.
2. Create `src/services/bds_client.py` with `BdsClient` class, `O(1)` dispatch table, `_reader_loop`, `execute`/`wait_for`/`send`/`subscribe`.
3. Add `src/services/__init__.py` export if needed.
4. Write `tests/test_bds_client.py` (unit without subprocess, feed fake lines, assert `HOLD_ACK` etc.)
5. Keep `src/server.py` emitting for now, but also instantiate `BdsClient` side-by-side and compare outputs (shadow mode).

### Phase B2 — Coordinator Swap

1. Update `src/services/backup_coordinator.py` to accept `BdsClient` (not `BdsAdapter`), change `run` to use `execute` directly.
2. Update `src/geode.py` to construct `BdsClient` and pass to coordinator.
3. Delete `src/services/bds_adapter.py` or keep as `BdsAdapter = BdsClient` alias for compat.
4. Run existing mocked coordinator tests `uv run --python 3.12 python -m pytest` (happy/retry/timeout/concurrent) — should pass without `emit('backup.hold')` mock, instead feed `BdsClient` queue.

### Phase B3 — Remove pyventus

1. Delete `parsers` list `src/server.py:52`, `__event_emitter` `src/server.py:33`, `events: EventLinker` `src/server.py:36`.
2. Move `on_player.connect` etc. `src/server.py:243` to `src/services/player_service.py` or keep in `server.py` but as `async def _handle_player(self, ev: BdsEvent)` called via `bds.subscribe`.
3. `src/server.py:86` `__server_output` deleted — `BdsClient._reader_loop` is the reader.
4. `uv run --python 3.12 python -m py_compile` + manual `emit` tests replaced with `bds._parse` tests.

### Phase B4 — Scheduler

1. Create `src/services/scheduler.py` as above.
2. Replace `src/handlers/loop.py` usage in `src/geode.py:75` and `src/geode.py:81` — remove `@looper.loop`, use `scheduler.add`.
3. Ensure `geode.log` rotation and `src/routes/*` still work (`GET /backups` `src/routes/backups.py:28` will call `coordinator.run`).

### Phase B5 — Config Typing

1. Replace `src/handlers/config.py:5` `UserDict` with `pydantic_settings.BaseSettings`:
   ```python
   class BackupConfig(BaseModel):
       hold_timeout_seconds: int = Field(default=45, ge=5, le=300)
       query_retry_interval_seconds: float = Field(default=2.5, ge=0.5, le=10)
   ```
2. Update `src/services/backup_coordinator.py: _timeouts()` to read from typed config, remove clamp.
3. Validate `config.default.yml` still loads via `yaml.safe_load` for backwards compat or migrate to `config.yml` env.

---

## 7. Testing & Verification

- Reuse Option A mocked tests (happy/retry/timeout/concurrent) but replace `server.emit('backup.hold', ...)` with `bds._queue.put(BdsEvent(HOLD_ACK, ...))` or `FakeBdsClient`.
- Add `tests/test_bds_client_dispatch.py`: feed raw BDS log lines from `geode.log` `geode.log.1` and assert O(1) parse → correct `BdsEventType`.
- Add `tests/test_scheduler_jitter.py`: verify `TaskGroup` cancellation propagates and hold always resumed.
- Manual: run with `backup.location: local` `config.default.yml:4`, stub BDS via `../server/bedrock_server` fake script that delays `save query` 10s → ensure coordinator timeout 45 still works.

---

## 8. Risks & Mitigations

- **Regex regression:** `EventParser` regexes (`player.connect` `r'Player connected: (.*), xuid: ([0-9]+)'` `src/server.py:54`) are battle-tested; re-implement with same regex per type, add snapshot tests from `geode.log`.
- **API compat:** `GET /info` `src/routes/info.py:44` returns `status`; keep `server.status` alias updated by coordinator (`started`/`backup`) or map `BackupState` → string.
- **Relay:** `src/handlers/relay.py:73` `relay_backup_timeout` already exists; ensure `discord_relay.relay_events.backups` check stays.
- **Rollback:** Each phase is behind feature flag `USE_BDS_CLIENT=0/1`; can revert to `develop` by checking out `src/server.py` from `develop`.

---

## 9. File Checklist for Future Session

- [ ] `docs/OPTION_B_PLAN.md` (this file)
- [ ] `src/services/bds_types.py` (new)
- [ ] `src/services/bds_client.py` (new)
- [ ] `src/services/scheduler.py` (new)
- [ ] Update `src/services/backup_coordinator.py` (exists from Option A)
- [ ] Update `src/server.py` (strip pyventus)
- [ ] Update `src/geode.py` (inject BdsClient)
- [ ] Update `src/handlers/config.py` (optional pydantic)
- [ ] Delete or alias `src/services/bds_adapter.py`
- [ ] Keep `src/handlers/loop.py` until B4

---

## 10. References

- Current Option A branch: `fix/backup-coordinator-a` (commit `33a7dba` base, uncommitted Option A files)
- Discarded duplicate fix: `fix/backup-hold-timeout` `3a37345` (had `_poller_task` + `_fallback_task` race)
- Key files: `src/server.py:52` parsers, `src/server.py:86` `__server_output`, `src/server.py:183` `emit`, `src/geode.py:47` `initiate_save`, `src/handlers/backup.py:186` `backup()`, `src/handlers/loop.py:50` loop, `src/handlers/config.py:5` UserDict, `config.default.yml:27`, `src/handlers/relay.py:73`
- Log samples: `geode.log`, `geode.log.1` (real BDS output for parser snapshot tests)

---

## 11. Minimal Prompt to Resume

> "Implement Option B per `docs/OPTION_B_PLAN.md` Phase B1. Start with `src/services/bds_types.py` and `src/services/bds_client.py`, keep `src/services/backup_coordinator.py` interface stable, use `fix/backup-coordinator-a` as base, do not commit until tests pass."

