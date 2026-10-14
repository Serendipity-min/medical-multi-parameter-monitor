"""agent-browser 本地交互回归；只连接 loopback 夹具，不调用正式 AI/监护接口。"""
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "cloud/evidence/p6-v2-ui"
CLI = os.environ.get("P6_BROWSER_CLI", "D:/Node/node_global/node_modules/agent-browser/bin/agent-browser-win32-x64.exe")
SESSION = "p6-v2"
URL = "http://127.0.0.1:18767/medical-monitor/"
checks = []


def cli(*args, source=None):
    r = subprocess.run([CLI, "--session", SESSION, "--json", *args], input=source, encoding="utf-8", capture_output=True, timeout=30)
    if r.returncode:
        raise RuntimeError(f"agent-browser {args[0]} failed (exit {r.returncode})")
    data = json.loads(r.stdout)
    if not data["success"]:
        raise RuntimeError(f"agent-browser {args[0]} failed")
    return data.get("data", {})


def js(source):
    return cli("eval", "--stdin", source=source).get("result")


def wait(expression, timeout=20):
    # 短轮询只限本机页面状态，不硬等服务或调用模型。
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if js(expression):
            return
        time.sleep(.1)
    raise AssertionError(f"UI wait failed: {expression}")


def check(name, expression):
    assert js(expression), name
    checks.append(name)
    print("PASS", name, flush=True)


def control(port=18766, **values):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/fixture/control", data=json.dumps(values).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def stats():
    with urllib.request.urlopen("http://127.0.0.1:18765/fixture/state") as r:
        return json.load(r)


def connect():
    cli("click", "#open-access")
    cli("fill", "#view-token", "local-monitor-fixture")
    cli("click", "#access-form button[type=submit]")
    wait("document.querySelector('#connection').textContent === '监护通道已连接'")


def ask(question, result="回答完成"):
    js("document.querySelector('.ai-access').open = true")
    cli("fill", "#ai-token", "local-ai-fixture")
    cli("fill", "#ai-question", question)
    cli("click", "#ai-send")
    wait(f"document.querySelector('#ai-status').textContent.includes({json.dumps(result)})")
    js("document.querySelector('.ai-access').open = false")


def shot(name):
    # 截图标签由测试注入，不进入产品代码，协议模拟不冒充真实模型验证。
    js("document.querySelector('.ai-heading p') && (document.querySelector('.ai-heading p').textContent = '本地 UI 验证 · MOCK 数据 / 2026-10-14 回放 · 本轮真实调用 0 次')")
    cli("screenshot", str(OUT / name))


def route(name):
    cli("click", f'[data-route="{name}"]')
    wait(f"location.hash === '#/{name}' && document.querySelector('.route-{name}') !== null")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    control(delay=0, validity="VALID", schema=False, voice="PAUSED")
    control(18765, validity="VALID")
    cli("set", "viewport", "1920", "1080")
    cli("open", URL + "#/ai")
    # open 相同 hash 在浏览器工具中可能只做软导航；显式 reload 才能验证刷新边界。
    cli("reload")
    wait("document.querySelector('#ai-token') !== null")
    check("direct_hash_route", "!!document.querySelector('#ai-title') && location.hash === '#/ai'")
    cli("snapshot", "-i")
    connect()
    baseline = stats()["connections"]
    for name in ["overview", "temp", "ecg", "spo2", "resp", "nibp", "ai"]:
        route(name)
        check(f"route_{name}_mounted", "document.querySelector('[aria-current=page]').dataset.route === location.hash.slice(2)")
    assert stats()["connections"] == baseline, "route switch reconstructed MonitorSocket"
    checks.append("single_monitor_socket_across_seven_routes")
    check("same_monitor_facts", "document.querySelector('[data-channel=HR] strong').textContent === '77 bpm' && document.querySelector('#ai-source').textContent.includes('模拟')")
    ask("确定性读数")
    check("deterministic_not_called", "document.querySelector('#ai-mode').textContent === '监护事实核对 · 本轮未调用模型'")
    ask("协议真实模型状态")
    check("real_used_protocol_fixture_only", "document.querySelector('#ai-mode').textContent === '本轮使用豆包' && document.querySelector('.ai-turn:last-child .ai-answer').textContent.includes('本地协议模拟')")
    ask("回放一般健康提示")
    check("recorded_answer_explicit_replay", "document.querySelector('#ai-mode').textContent.includes('历史回答回放') && document.querySelector('.ai-turn:last-child').textContent.includes('REPLAY')")
    shot("ai-replay-1920.png")
    saved = js("document.querySelector('#ai-history').textContent")
    route("overview")
    wait("document.querySelector('#value-HR').textContent === '77'")
    cli("screenshot", str(OUT / "overview-after-1920.png"))
    check("canvas_resumes_after_ai", "[...document.querySelectorAll('canvas')].length === 3 && [...document.querySelectorAll('canvas')].every(c=>c.width>0 && c.height>0)")
    route("ai")
    assert js("document.querySelector('#ai-history').textContent") == saved
    checks.append("single_chat_session_retained")
    ask("模拟读数")
    check("mock_source_label", "document.querySelector('#ai-mode').textContent.includes('MOCK') && document.querySelector('#ai-current-facts').textContent.includes('synthetic')")
    # 每种下发回执由协议夹具返回，永不连接真实 Broker/设备。
    cli("check", "#ai-voice")
    for voice in ["DISABLED", "BROKER_PUBACK_ONLY", "RATE_LIMITED", "DOWNLINK_FAILED"]:
        control(voice=voice)
        ask("播报状态")
        check("voice_" + voice, f"document.querySelector('#ai-voice-status').textContent.startsWith('{voice}') && !document.querySelector('#ai-voice-status').textContent.includes('已播放')")
    cli("uncheck", "#ai-voice")
    ask("暂停播报")
    check("voice_PAUSED", "document.querySelector('#ai-voice-status').textContent.startsWith('PAUSED')")
    control(18765, validity="STALE")
    control(validity="STALE")
    wait("document.querySelector('[data-channel=HR] strong').textContent === '-- bpm'")
    ask("过期读数")
    check("stale_without_current_value", "document.querySelector('.ai-turn:last-child .ai-answer').textContent.includes('STALE / OFFLINE') && document.querySelector('[data-channel=HR] strong').textContent.includes('--')")
    shot("ai-stale-1920.png")
    control(18765, validity="VALID")
    control(validity="VALID")
    cli("click", "#open-access")
    cli("click", "#disconnect")
    js("document.querySelector('#access-dialog').close()")
    check("offline_clears_current_facts", "document.querySelector('[data-channel=HR] strong').textContent.includes('--') && document.querySelector('#ai-source').textContent.includes('已断开')")
    connect()
    cli("click", "#freeze")
    check("freeze_indicator_shared", "document.querySelector('#freeze').getAttribute('aria-pressed') === 'true' && !document.querySelector('#frozen-status').hidden")
    route("overview")
    check("freeze_survives_route_switch", "document.querySelector('#freeze').getAttribute('aria-pressed') === 'true' && document.querySelector('#value-HR').textContent === '77'")
    cli("click", "#freeze")
    route("ai")
    js("document.querySelector('.ai-access').open = true")
    cli("fill", "#ai-token", "invalid-local-fixture")
    cli("fill", "#ai-question", "认证失败")
    cli("click", "#ai-send")
    wait("document.querySelector('#ai-status').textContent.includes('验证失败')")
    checks.append("independent_ai_auth_failure")
    assert stats()["active"] == 1
    cli("fill", "#ai-token", "local-ai-fixture")
    control(delay=3)
    cli("fill", "#ai-question", "取消测试")
    cli("click", "#ai-send")
    cli("click", "#ai-cancel")
    wait("document.querySelector('#ai-status').textContent === '已取消回答'")
    checks.append("cancel_request")
    control(delay=17)
    ask("超时测试", "回答超时")
    checks.append("timeout_15_seconds")
    control(delay=0, schema=True)
    ask("错网关回执", "回执不匹配")
    checks.append("wrong_gateway_response_rejected")
    control(schema=False, delay=3)
    cli("fill", "#ai-question", "离页取消")
    cli("click", "#ai-send")
    route("overview")
    route("ai")
    wait("document.querySelector('.ai-turn:last-child .ai-answer').textContent === '已取消回答'")
    checks.append("leaving_route_cancels_response")
    # 换网关会清空聊天、重建 AI 会话，待答结果不得跨网关回填。
    cli("fill", "#ai-question", "换网关取消")
    cli("click", "#ai-send")
    cli("click", "#open-access")
    cli("select", "#gateway-select", "GW-C-001")
    js("document.querySelector('#access-dialog').close()")
    wait("document.querySelector('#ai-gateway').textContent === 'GW-C-001'")
    wait("document.querySelectorAll('.ai-turn').length === 0 && !document.querySelector('#ai-send').disabled")
    check("gateway_change_isolates_chat_and_voice", "document.querySelectorAll('.ai-turn').length === 0 && !document.querySelector('#ai-voice').checked")
    control(delay=0)
    ask("长文本")
    check("long_text_is_plain_text", "document.querySelector('.ai-answer').textContent.includes('<img') && !document.querySelector('.ai-answer img') && document.querySelector('.ai-answer').textContent.length>3000")
    shot("ai-long-text-1920.png")
    for _ in range(9):
        ask("模拟读数")
    check("history_bounded_eight_turns", "document.querySelectorAll('.ai-turn').length === 8")
    ask("回放一般健康提示")
    cli("set", "viewport", "390", "844")
    js("document.querySelector('#route-view').scrollTop=0; document.querySelector('#ai-history').scrollTop=document.querySelector('#ai-history').scrollHeight")
    check("mobile_no_horizontal_overflow", "document.documentElement.scrollWidth === innerWidth && document.querySelector('#route-view').scrollWidth <= document.querySelector('#route-view').clientWidth")
    shot("ai-mobile-390.png")
    js("document.querySelector('#ai-form').scrollIntoView({block:'end'})")
    shot("ai-mobile-composer-390.png")
    js("document.querySelector('.ai-current').scrollIntoView({block:'start'})")
    shot("ai-mobile-facts-390.png")
    js("document.querySelector('.ai-playback').scrollIntoView({block:'end'})")
    shot("ai-mobile-voice-390.png")
    cli("set", "viewport", "844", "390")
    check("landscape_no_horizontal_overflow", "document.documentElement.scrollWidth === innerWidth")
    shot("ai-landscape-844.png")
    cli("set", "viewport", "1280", "720")
    # 1024x576 相当于 1280x720 浏览器 125% 缩放的 CSS 视口，再对实际缩放截图。
    js("document.documentElement.style.zoom='1.25'; document.querySelector('#route-view').scrollTop=0")
    check("125_percent_zoom_no_overflow", "document.documentElement.scrollWidth <= innerWidth && document.querySelector('#route-view').scrollWidth <= document.querySelector('#route-view').clientWidth")
    shot("ai-125-percent-1280.png")
    js("document.documentElement.style.zoom=''; document.querySelector('#ai-question').focus()")
    cli("press", "Tab")
    check("keyboard_focus_reaches_composer_action", "['ai-send','ai-cancel'].includes(document.activeElement.id)")
    cli("open", URL + "#/ai")
    cli("reload")
    wait("document.querySelector('#ai-token') !== null")
    check("refresh_keeps_hash_clears_credentials_and_history", "location.hash === '#/ai' && document.querySelector('#ai-token').value === '' && document.querySelectorAll('.ai-turn').length === 0 && document.querySelector('#connection').textContent === '未连接'")
    cli("set", "viewport", "1920", "1080")
    shot("ai-empty-1920.png")
    result = dict(result="PASS", exit_code=0, checks=checks, real_calls=0, provenance="local MOCK / protocol fixture / explicitly labelled 2026-10-14 recording replay", monitor_stats=stats())
    (OUT / "browser-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("UI PASS",len(checks),"checks; real calls 0")


if __name__ == "__main__":
    main()
