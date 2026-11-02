"""真实C音频块的有界重组；调用者按认证主题隔离C与Host正例。"""
import hashlib
import struct
import time
import zlib

HEADER=struct.Struct('<4sIHHIIIIHBB')


class AudioAssembler:
    def __init__(self):
        self.active={}
        self.completed={}

    def discard(self,source):
        self.active.pop(source,None)

    def feed(self,source,packet,now=None):
        now=time.monotonic() if now is None else now
        if len(packet)!=544:raise ValueError('MIC_PACKET_LENGTH')
        magic,session,seq,total,rate,bytes_,whole,crc,length,flags,codec=HEADER.unpack_from(packet)
        data=packet[32:]
        if (magic!=b'MC01' or not session or total!=125 or rate!=16000 or bytes_!=64000 or length!=512 or
            codec!=1 or seq>=total or flags!=((1 if seq==0 else 0)|(2 if seq==124 else 0)) or
            zlib.crc32(data)!=crc):
            raise ValueError('MIC_PACKET_FIELDS_OR_CRC')
        if (source,session) in self.completed:raise ValueError('MIC_COMPLETED_SESSION_REPLAY')
        current=self.active.get(source)
        if seq==0 and current is None:
            current={'session':session,'crc':whole,'at':now,'blocks':[]};self.active[source]=current
        if current is None or current['session']!=session or current['crc']!=whole or now-current['at']>=90:
            self.discard(source);raise ValueError('MIC_SESSION_OR_EXPIRY')
        if seq<len(current['blocks']):
            if current['blocks'][seq]!=data:
                self.discard(source);raise ValueError('MIC_CHANGED_DUPLICATE')
            return None
        if seq!=len(current['blocks']):
            self.discard(source);raise ValueError('MIC_MISSING_OR_OUT_OF_ORDER')
        current['blocks'].append(data)
        if seq!=124:return None
        pcm=b''.join(current['blocks']);self.discard(source)
        if len(pcm)!=64000 or zlib.crc32(pcm)!=whole:raise ValueError('MIC_WHOLE_AUDIO_CRC')
        # 只保留最近完成身份；音频不驻留重放表。
        self.completed={k:t for k,t in self.completed.items() if now-t<300}
        self.completed[(source,session)]=now
        return {'source':source,'session':session,'crc32':whole,'rate':rate,'chunks':total,
                'PCM_SHA256':hashlib.sha256(pcm).hexdigest(),'pcm':pcm}


def reply_packet(session,audio_crc,text):
    import unicodedata
    raw=text.encode('utf-8')
    if not 1<=len(raw)<=60 or any(unicodedata.category(c).startswith('C') or c in '[]' for c in text):
        raise ValueError('MIC_REPLY_TEXT')
    return struct.pack('<4sIIHH',b'MR01',session,audio_crc,len(raw),0)+raw
