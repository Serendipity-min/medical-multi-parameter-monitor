"""仅loopback的HTTPS等效入口：真实dist及真实AI/Backend前缀路由，不替换正式Nginx。"""
import asyncio
from pathlib import Path
import httpx
from fastapi import FastAPI,Request,WebSocket
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from websockets.asyncio.client import connect

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)


@app.api_route('/medical-monitor/ai/{tail:path}',methods=['GET','POST'])
@app.api_route('/medical-monitor/api/{tail:path}',methods=['GET'])
async def proxy(request:Request,tail:str):
    path=request.url.path
    ai=path.startswith('/medical-monitor/ai/')
    target='http://127.0.0.1:'+('18766' if ai else '18765')+(path if ai else path.removeprefix('/medical-monitor'))
    # 保留AI完整前缀，Backend剥离项目路径；只转发必要头，不记录请求正文/令牌。
    headers={k:v for k,v in request.headers.items() if k in ('authorization','content-type','origin')}
    async with httpx.AsyncClient(timeout=18) as client:
        response=await client.request(request.method,target,headers=headers,content=await request.body())
    returned={k:v for k,v in response.headers.items() if k=='content-type' or k.startswith('access-control-')}
    return Response(response.content,status_code=response.status_code,headers=returned)


@app.websocket('/medical-monitor/ws/v1/monitor')
async def monitor(front:WebSocket):
    await front.accept();tasks=set()
    try:
        async with connect('ws://127.0.0.1:18765/ws/v1/monitor',origin=front.headers.get('origin'),max_size=65536) as back:
            async def up():
                while True:await back.send(await front.receive_text())
            async def down():
                async for message in back:await front.send_text(message)
            tasks={asyncio.create_task(up()),asyncio.create_task(down())}
            done,_=await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            for task in done:task.result()
    except Exception:
        # 关闭任一端就回收另一端，不以重连或缓存伪造连接正常。
        pass
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        try:await front.close()
        except RuntimeError:pass

app.mount('/medical-monitor',StaticFiles(directory=Path(__file__).resolve().parents[1]/'dist',html=True),name='web')
