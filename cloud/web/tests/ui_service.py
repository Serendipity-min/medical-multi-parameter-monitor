"""真实既有 AI 应用的本机 MOCK 整合验证；SnapshotReader 读取合成监护 WS。"""
import json
from ui_browser import OUT, URL, check, cli, connect, control, js, shot, wait, checks


def main():
    cli("set", "viewport", "1920", "1080")
    cli("open", URL + "#/ai")
    cli("reload")
    wait("document.querySelector('#ai-token') !== null")
    connect()
    js("document.querySelector('.ai-access').open=true")
    cli("fill", "#ai-token", "local-ai-service-" + "x" * 32)
    for name, validity, question, voice in [
        ("actual_service_deterministic", "VALID", "现在心率多少", False),
        ("actual_service_general_health_mock", "VALID", "久坐办公有哪些一般健康提示", False),
        ("actual_service_voice_disabled", "VALID", "解释当前数据来源", True),
        ("actual_service_invalid_no_value", "INVALID", "现在心率多少", False),
        ("actual_service_offline_no_value", "OFFLINE", "现在心率多少", False),
    ]:
        control(18765, validity=validity)
        js(f"document.querySelector('#ai-voice').checked={str(voice).lower()}")
        cli("fill", "#ai-question", question)
        cli("click", "#ai-send")
        wait("document.querySelector('#ai-status').textContent.includes('回答完成')")
        if validity == "VALID":
            check(name, "document.querySelector('.ai-turn:last-child .ai-answer').textContent.includes('77') && document.querySelector('#ai-mode').textContent.includes('MOCK')")
        else:
            check(name, f"document.querySelector('.ai-turn:last-child .ai-answer').textContent.includes('{validity}') && document.querySelector('[data-channel=HR] strong').textContent === '-- bpm'")
        if voice:
            check("actual_service_voice_has_no_broker", "document.querySelector('#ai-voice-status').textContent.startsWith('DISABLED')")
    control(18765, validity="VALID")
    wait("document.querySelector('[data-channel=HR] strong').textContent === '77 bpm'")
    cli("fill", "#ai-question", "现在心率多少")
    cli("click", "#ai-send")
    wait("document.querySelector('#ai-status').textContent.includes('回答完成')")
    js("document.querySelector('.ai-access').open=false")
    shot("ai-service-mock-1920.png")
    # 仅保存文字回执及状态，不导出请求头/令牌或浏览器会话。
    result = {"result":"PASS", "exit_code":0, "checks":checks, "real_calls":0,
              "service":"existing cloud.ai.app, MOCK provider, MONITOR reader over local fixture WS, MQTT disabled",
              "last_answer":js("document.querySelector('.ai-turn:last-child').textContent")}
    (OUT/"service-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Existing AI service MOCK UI PASS",len(checks),"checks")


if __name__ == "__main__":
    main()
