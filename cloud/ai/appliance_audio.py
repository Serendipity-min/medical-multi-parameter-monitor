"""音频→ASR→事实API的隔离连接点；ASR/HTTP端口注入，禁止从音频推测测量值。"""
import asyncio


class AudioFactFlow:
    def __init__(self, replies, transcribe, ask):
        self.replies, self.transcribe, self.ask = replies, transcribe, ask

    async def feed(self, topic, packet, qos=1, retain=False):
        audio = self.replies.feed_audio(topic, packet, qos, retain)
        if audio is None:
            return None
        context = self.replies.recording
        try:
            async with asyncio.timeout(90):
                question = await self.transcribe(audio['pcm'], audio['rate'])
            if not isinstance(question, str) or not question.strip() or len(question) > 200:
                raise ValueError('ASR_NO_ACCEPTABLE_TEXT')
            if self.replies.clock_ms() >= context.deadline:
                raise ValueError('AUDIO_TURN_EXPIRED')
            # ask只传问题；读取快照/数值模板/最终时效复核由原API负责。
            return await self.ask(question.strip())
        finally:
            if self.replies.recording is context:
                self.replies.recording = None
