import os, time, httpx
from nexuscore import AuthenticatedClient

TOKEN_URL = "http://nexuscore:8000/api/auth/token"
CLIENT_ID = os.environ.get("NEXUSCORE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("NEXUSCORE_CLIENT_SECRET")

class _ScopedToken:
    """Holds a cached token + client for a single guild scope."""
    def __init__(self):
        self.expires_at: float = 0
        self.client: AuthenticatedClient | None = None

class ManagedAPIClient:
    def __init__(self):
        self._token: _ScopedToken | None = None

    async def _refresh(self) -> _ScopedToken:
        data = {"grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET}

        async with httpx.AsyncClient() as http:
            resp = await http.post(TOKEN_URL, data=data)
            resp.raise_for_status()
            payload = resp.json()

        scoped = _ScopedToken()
        scoped.expires_at = time.time() + payload.get("expires_in", 3600)
        scoped.client = AuthenticatedClient(
            base_url="http://nexuscore:8000/api",
            token=payload["access_token"]
        )
        self._token = scoped
        return scoped

    async def get(self) -> AuthenticatedClient:
        scoped = self._token

        if scoped is None or time.time() >= scoped.expires_at - 30:
            scoped = await self._refresh()
        return scoped.client