import asyncio
import websockets
import json
import os
from typing import List, Dict, Any
from ..config import DERIV_APP_ID

class DerivClient:
    def __init__(self):
        self.url = f"wss://ws.derivws.com/websockets/v3?app_id={DERIV_APP_ID}"

    async def _send(self, ws, data: dict):
        await ws.send(json.dumps(data))

    async def get_candles(self, symbol: str, granularity: int, count: int = 120) -> List[Dict[str, Any]]:
        """
        Return candles sorted ASC (old->new), each: {epoch, open, high, low, close}
        """
        async with websockets.connect(self.url) as ws:
            req = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": count,
                "end": "latest",
                "start": 1,
                "granularity": granularity,
                "style": "candles"
            }
            await self._send(ws, req)
            resp = await ws.recv()
            data = json.loads(resp)

            if "candles" not in data:
                raise ValueError(f"Failed to get candles: {data}")

            candles = []
            for c in data["candles"]:
                candles.append({
                    "epoch": c["epoch"],
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                })
            candles.sort(key=lambda x: x["epoch"])
            return candles

# Backward-compatible wrapper
_client_instance = DerivClient()

async def get_candles(symbol: str, granularity: int, count: int = 120):
    return await _client_instance.get_candles(symbol, granularity, count)

if __name__ == "__main__":
    async def _t():
        print(await get_candles("frxEURUSD", 300, 5))
    asyncio.run(_t())
