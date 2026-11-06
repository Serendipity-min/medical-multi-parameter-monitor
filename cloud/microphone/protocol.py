"""真实C音频块的有界重组；调用者按认证主题隔离C与Host正例。"""
import hashlib
import struct
import time
import zlib

HEADER=struct.Struct('<4sIHHIIIIHBB')


class AudioAssembler:
    def __init__(self,timeout_s=90):
        self.timeout_s=timeout_s
        self.active={}
        self.completed={}

    def discard(self,source):
        self.active.pop(source,None)

    def feed(self,source,packet,now=None):
        now=time.monotonic() if now is None else now
        if len(packet)!=544:raise ValueError('MIC_PACKET_LENGTH')
        magic,session,seq,total,rate,bytes_,whole,crc,length,flags,codec=HEADER.unpack_from(packet)
        if (magic not in (b'MC01',b'MC02') or not session or rate!=16000 or codec!=1 or
            not 32000<=bytes_<=64000 or bytes_%2 or total!=(bytes_+511)//512 or seq>=total or
            length!=min(512,bytes_-seq*512) or
            magic==b'MC01' and (bytes_!=64000 or length!=512) or
            flags!=((1 if seq==0 else 0)|(2 if seq+1==total else 0))):
            raise ValueError('MIC_PACKET_FIELDS_OR_CRC')
        data=packet[32:32+length]
        if any(packet[32+length:]) or zlib.crc32(data)!=crc:
            raise ValueError('MIC_PACKET_FIELDS_OR_CRC')
        if (source,session) in self.completed:raise ValueError('MIC_COMPLETED_SESSION_REPLAY')
        current=self.active.get(source)
        # 经校验的新起始块可取代中断会话；同会话重复不延长装配期限。
        if seq==0 and (current is None or session>current['session']):
            current={'session':session,'crc':whole,'bytes':bytes_,'magic':magic,'at':now,'blocks':[]};self.active[source]=current
        if (current is None or current['session']!=session or current['crc']!=whole or
            current['bytes']!=bytes_ or current['magic']!=magic or now-current['at']>=self.timeout_s):
            self.discard(source);raise ValueError('MIC_SESSION_OR_EXPIRY')
        if seq<len(current['blocks']):
            if current['blocks'][seq]!=data:
                self.discard(source);raise ValueError('MIC_CHANGED_DUPLICATE')
            return None
        if seq!=len(current['blocks']):
            self.discard(source);raise ValueError('MIC_MISSING_OR_OUT_OF_ORDER')
        current['blocks'].append(data)
        if seq+1!=total:return None
        pcm=b''.join(current['blocks']);self.discard(source)
        if len(pcm)!=bytes_ or zlib.crc32(pcm)!=whole:raise ValueError('MIC_WHOLE_AUDIO_CRC')
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
