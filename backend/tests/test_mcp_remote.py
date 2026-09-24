"""원격 MCP(/mcp) 엔드포인트를 MCP JSON-RPC 메시지로 직접 호출해 본다."""

from fastapi.testclient import TestClient

import main

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
           "MCP-Protocol-Version": "2025-06-18"}


def rpc(client, method, params=None, id_=1):
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    res = client.post("/mcp", json=body, headers=HEADERS)
    assert res.status_code == 200, res.text
    return res.json()


def test_remote_mcp_tools():
    # lifespan(세션 관리자 실행)이 돌도록 with 로 연다
    with TestClient(main.app) as client:
        init = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                          "clientInfo": {"name": "pytest", "version": "0"}})
        assert init["result"]["serverInfo"]["name"] == "geulbeot"

        names = {t["name"] for t in rpc(client, "tools/list", id_=2)["result"]["tools"]}
        assert {"get_data_summary", "search_works", "analyze_text", "add_writing_record"} <= names

        call = rpc(client, "tools/call", {"name": "analyze_text",
                                          "arguments": {"text": "그리고 갔다. 그리고 왔다. 그리고 잤다."}}, id_=3)
        assert call["result"]["isError"] is False
        assert '"그리고": 3' in call["result"]["content"][0]["text"]

        # 허용되지 않은 Host 는 DNS 리바인딩 방어로 거부
        bad = client.post("/mcp", json={"jsonrpc": "2.0", "id": 9, "method": "tools/list"},
                          headers={**HEADERS, "Host": "evil.example.com"})
        assert bad.status_code in (400, 421)
