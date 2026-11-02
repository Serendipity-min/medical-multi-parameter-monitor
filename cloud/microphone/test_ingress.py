"""正常持续传输不受连接总时长限制，真正无数据才超时；纯Host。"""
import asyncio
import unittest
import ingress


class Writer:
    def __init__(self):self.data=bytearray()
    def write(self,data):self.data.extend(data)
    async def drain(self):pass


class IngressTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_stream_outlives_idle_budget(self):
        old=ingress.IDLE_TIMEOUT_SECONDS;ingress.IDLE_TIMEOUT_SECONDS=.1
        reader=asyncio.StreamReader();writer=Writer()
        async def feed():
            for _ in range(4):await asyncio.sleep(.04);reader.feed_data(b'pcm')
            reader.feed_eof()
        try:
            await asyncio.gather(feed(),ingress.copy(reader,writer))
            self.assertEqual(writer.data,b'pcm'*4)
        finally:ingress.IDLE_TIMEOUT_SECONDS=old

    async def test_idle_read_expires(self):
        old=ingress.IDLE_TIMEOUT_SECONDS;ingress.IDLE_TIMEOUT_SECONDS=.05
        try:
            with self.assertRaises(TimeoutError):await ingress.copy(asyncio.StreamReader(),Writer())
        finally:ingress.IDLE_TIMEOUT_SECONDS=old


if __name__=='__main__':unittest.main()
