"""隔离语音台架专用TCP透传；TLS仍由原隔离Broker终止，不解密或记录音频。"""
import asyncio


async def main():
    active=0

    async def accept(reader,writer):
        nonlocal active
        if active>=2:
            writer.close();await writer.wait_closed();return
        active+=1;upstream=None;copies=[]
        try:
            async with asyncio.timeout(180):
                remote,upstream=await asyncio.open_connection('127.0.0.1',18884)

                async def copy(source,target):
                    while data:=await source.read(16384):
                        target.write(data);await target.drain()

                copies=[asyncio.create_task(copy(reader,upstream)),asyncio.create_task(copy(remote,writer))]
                done,_=await asyncio.wait(copies,return_when=asyncio.FIRST_COMPLETED)
                for task in done:task.result()
        except (OSError,TimeoutError):
            print('MIC_INGRESS_CONNECTION_FAILED',flush=True)
        finally:
            for task in copies:task.cancel()
            if copies:await asyncio.gather(*copies,return_exceptions=True)
            writer.close()
            if upstream:upstream.close()
            active-=1

    server=await asyncio.start_server(accept,'0.0.0.0',1883,backlog=2)
    print('MIC_INGRESS_READY TCP1883_TO_ISOLATED_TLS18884',flush=True)
    async with server:await server.serve_forever()


if __name__=='__main__':asyncio.run(main())
