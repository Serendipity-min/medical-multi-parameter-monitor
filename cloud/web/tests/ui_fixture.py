"""仅供本机 UI 验证：合成监护帧和协议回执，不导入模型 Provider、不连接 Broker。"""
import asyncio
import copy
import hashlib
import json
import math
import time
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

app = FastAPI()
state = {"connections": 0, "active": 0, "requests": 0, "validity": "VALID", "voice": "PAUSED", "delay": 0, "schema": False}
recording = Path(__file__).resolve().parents[2] / "evidence/p6-v1-real-20261014/browser-response.json"


def snapshot(gateway: str):
    now = int(time.time() * 1000)
    specs = [("HR", 77, "bpm"), ("SPO2", 96, "%"), ("PR", 77, "bpm"),
             ("RR", 14, "breaths/min"), ("TEMP", 36.7, "degC"), ("NIBP", [112, 72], "mmHg"),
             ("ECG", None, "relative"), ("PPG", None, "relative"), ("RESP", None, "relative")]
    streams = []
    for name, value, unit in specs:
        rate = 250 if name == "ECG" else 50 if name in {"PPG", "RESP"} else 0
        streams.append(dict(gateway_id=gateway, node_id="NODE-A" if name in {"SPO2", "PR", "NIBP", "PPG"} else "NODE-B",
                            stream=name, timestamp=now, seq=now // 500, session_id="local-ui-fixture",
                            validity=state["validity"], source="MOCK", synthetic=True, value=value,
                            samples=[math.sin((now / 1000 + i / rate) * 6) for i in range(rate // 2)] if rate else [],
                            sample_rate=rate, unit=unit))
    return dict(type="snapshot", schema_version=1, gateway_id=gateway, gateway_state="ONLINE",
                nodes={"NODE-A": "ONLINE", "NODE-B": "ONLINE"}, server_time=now, broker_connected=True, streams=streams, replay=None, event=None)


@app.websocket("/ws/v1/monitor")
async def monitor(ws: WebSocket):
    await ws.accept()
    auth = await ws.receive_json()
    # 长合成令牌供原 AI SnapshotReader 使用，短令牌供浏览器协议测试；均无生产权限。
    if auth.get("token") not in {"local-monitor-fixture", "local-monitor-fixture-" + "x" * 32}:
        await ws.close(1008)
        return
    state["connections"] += 1
    state["active"] += 1
    try:
        while True:
            await ws.send_json(snapshot(auth["gateway_id"]))
            await asyncio.sleep(.5)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        state["active"] -= 1


@app.post("/fixture/control")
async def control(request: Request):
    # 控制口只存在于 loopback 测试进程；不接受任意文件路径、主机或模型配置。
    for key, value in (await request.json()).items():
        if key in {"validity", "voice", "delay", "schema"}:
            state[key] = value
    return state


@app.get("/fixture/state")
async def stats():
    return state


@app.post("/api/v1/text")
async def answer(request: Request):
    state["requests"] += 1
    if request.headers.get("authorization") != "Bearer local-ai-fixture":
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    await asyncio.sleep(state["delay"])
    if body["question"] == "回放一般健康提示":
        data = copy.deepcopy(json.loads(recording.read_text(encoding="utf-8")))
        # 保留真实答案和回执，显式改为历史来源，不能冒充当前读数或本轮真实调用。
        data["answer"] = "【2026-10-14 真实回答回放；本轮未调用模型】\n" + data["answer"]
        for fact in data["facts"]:
            fact["source"] = "REPLAY"
    else:
        facts = [{**item, "gateway_id": body["gateway_id"], "label": item["stream"]} for item in snapshot(body["gateway_id"])["streams"] if not item["sample_rate"]]
        text = "监护事实核对：心率 77 bpm。MOCK / synthetic，非真人测量。"
        if state["validity"] != "VALID":
            text = "当前读数 STALE / OFFLINE，不提供当前数值，请先检查监护连接。"
        if body["question"] == "长文本":
            text = ("长文本布局验证：<img src=x onerror=alert(1)> 仅作为文字。\n" + "连续标识" * 60 + "\n") * 14
        data = dict(answer=text, answer_kind="DETERMINISTIC", facts=facts, fact_digest=hashlib.sha256(text.encode()).hexdigest()[:32],
                    model_mode="MOCK", real_model="NOT_CALLED", model_evidence=None, model_input_fact_digest=None)
        if body["question"] == "协议真实模型状态":
            data.update(model_mode="REAL", real_model="REAL_REQUEST_USED", answer_kind="VERIFIED_EXPLANATION",
                        answer="【本地协议模拟；没有调用模型】真实模型状态字段的 UI 回归。",
                        model_evidence={"requested_model": "doubao-seed-2-0-mini-260428", "status": "VALIDATED"})
        elif body["question"] == "确定性读数":
            data["model_mode"] = "REAL"
    data.update(session_id=body["session_id"], gateway_id="wrong-gateway" if state["schema"] else body["gateway_id"],
                turn_id=f"local-turn-{state['requests']}", voice_status=state["voice"] if body["voice"] else "PAUSED")
    return data
