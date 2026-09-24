"""실제 MCP 클라이언트(ClientSession)로 글벗 MCP 서버의 도구를 호출해 본다.

두 가지 연결 방식을 모두 검증한다.
  원격 (Streamable HTTP): python -m scripts.mcp_smoke_test https://geulbeot-api.onrender.com/mcp
  로컬 (stdio)          : python -m scripts.mcp_smoke_test https://geulbeot-api.onrender.com
      → mcp_server.py 를 자식 프로세스로 띄우고, 그 서버가 주어진 REST API 를 호출한다.
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

TARGET = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
SERVER = Path(__file__).resolve().parent.parent / "mcp_server.py"


def short(result, limit=200) -> str:
    text = " ".join(c.text for c in result.content if getattr(c, "text", None))
    return " ".join(text.split())[:limit]


@asynccontextmanager
async def connect():
    if TARGET.endswith("/mcp"):
        async with streamable_http_client(TARGET) as (read, write, *_):
            yield read, write, f"원격 Streamable HTTP · {TARGET}"
    else:
        params = StdioServerParameters(
            command=sys.executable, args=[str(SERVER)],
            env={**os.environ, "GEULBEOT_API_URL": TARGET, "PYTHONIOENCODING": "utf-8"},
        )
        async with stdio_client(params) as (read, write):
            yield read, write, f"로컬 stdio · mcp_server.py → {TARGET}"


async def main() -> None:
    async with connect() as (read, write, mode):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"연결: {mode} · 서버 이름: {init.server_info.name}")
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
