"""MCP 서버(mcp_server.py)를 stdio 로 띄워 실제 MCP 클라이언트처럼 도구를 호출해 본다.

실행 (backend 폴더에서):
    python -m scripts.mcp_smoke_test https://geulbeot-api.onrender.com
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

API_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SERVER = Path(__file__).resolve().parent.parent / "mcp_server.py"


def short(result, limit=220) -> str:
    text = " ".join(c.text for c in result.content if getattr(c, "text", None))
    return text.replace("\n", " ")[:limit]


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable, args=[str(SERVER)],
        env={**os.environ, "GEULBEOT_API_URL": API_URL, "PYTHONIOENCODING": "utf-8"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"서버: {init.server_info.name} · 연결 대상 API: {API_URL}")
            tools = await session.list_tools()
            print("도구:", ", ".join(t.name for t in tools.tools))
            calls = [
                ("get_data_summary", {}),
                ("get_statistics", {"group": "decade", "genre": "시"}),
                ("search_works", {"keyword": "고향", "genre": "시", "limit": 2}),
                ("list_conversations", {"limit": 3}),
            ]
            for name, args in calls:
                result = await session.call_tool(name, args)
                status = "오류" if result.is_error else "성공"
                print(f"- {name}({json.dumps(args, ensure_ascii=False)}) → {status}: {short(result)}")


if __name__ == "__main__":
    asyncio.run(main())
