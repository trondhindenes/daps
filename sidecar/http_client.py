from enum import Enum

import aiohttp


class HttpMethod(Enum):
    get = "GET"
    post = "POST"


class Http:
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *err):
        await self._session.close()
        self._session = None

    async def invoke(self, method: HttpMethod, url, body: dict = None, headers: dict = None):
        if method == HttpMethod.get:
            return await self.get(url, headers)
        elif method == HttpMethod.post:
            return await self.post(url, body, headers)

    async def get(self, url, headers):
        async with self._session.get(url) as resp:
            resp.raise_for_status()
            response_json = await resp.json()
            response_status = resp.status
            return response_status, response_json

    async def post(self, url, body: dict = None, headers: dict = None):
        async with self._session.post(url, json=body) as resp:
            resp.raise_for_status()
            response_json = await resp.json()
            response_status = resp.status
            return response_status, response_json
