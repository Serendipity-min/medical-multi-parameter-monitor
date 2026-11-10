/* 只保存时序和标识，不保留 MQTT 或 AT 内容。 */
enum { TXCHECK_PACKETS=16, TXCHECK_ACKS=256, TXCHECK_HISTORY_MS=16000, TXCHECK_CONTROL=255 };
typedef struct {
    uint32_t at,seq,gap,duration;
    uint16_t required,written;
    uint8_t type,stream;
} TxCheckPacket;
typedef struct {
    uint32_t at,delay,interval;
    uint16_t id;
} TxCheckAck;
typedef struct {
    TxCheckPacket packet;
    const unsigned char *data;
    uint32_t last;
    bool txe_timeout;
} TxCheckFlight;
static TxCheckFlight *txcheck_active;
static struct {
    TxCheckPacket packets[TXCHECK_PACKETS];
    TxCheckAck acks[TXCHECK_ACKS];
    uint32_t packet_next,ack_next,bytes,count,short_write,txe_timeout,gap,reentry,ack_gap,last_write;
    uint32_t reentry_at,reentry_outer_seq,reentry_inner_seq;
    unsigned reentry_outer_stream,reentry_inner_stream,reentry_poll;
} txcheck;

static void txcheck_enter(void){
    txcheck.packet_next=txcheck.ack_next=0;
}

static void txcheck_note_reentry(unsigned type){
    if(!txcheck_active)return;
    txcheck.reentry++;
    if(txcheck.reentry!=1)return;
    txcheck.reentry_at=g_uptime_ms;
    txcheck.reentry_outer_seq=txcheck_active->packet.seq;
    txcheck.reentry_outer_stream=txcheck_active->packet.stream;
    txcheck.reentry_inner_seq=type==3?io_metrics.frame_seq:0;
    txcheck.reentry_inner_stream=type==3?io_metrics.stream:TXCHECK_CONTROL;
    txcheck.reentry_poll=polling!=0;
}

static void txcheck_finish(TxCheckFlight *f,unsigned written){
    TxCheckPacket *p=&f->packet;
    p->written=written;p->duration=g_uptime_ms-p->at;
    txcheck.packets[txcheck.packet_next++%TXCHECK_PACKETS]=*p;
    txcheck.bytes+=written;txcheck.count++;
    txcheck.short_write+=written!=p->required;
    txcheck.txe_timeout+=f->txe_timeout;
    if(p->gap>txcheck.gap)txcheck.gap=p->gap;
    if(written)txcheck.last_write=f->last;
}

uint32_t platform_txcheck_written_at(void){return txcheck.last_write;}

void platform_txcheck_ack(uint16_t id,uint32_t written_at){
    uint32_t now=g_uptime_ms,interval=0;
    if(txcheck.ack_next){
        interval=now-txcheck.acks[(txcheck.ack_next-1u)%TXCHECK_ACKS].at;
        if(interval>txcheck.ack_gap)txcheck.ack_gap=interval;
    }
    txcheck.acks[txcheck.ack_next++%TXCHECK_ACKS]=(TxCheckAck){now,now-written_at,interval,id};
}

static void txcheck_format(char *line,size_t size,uint32_t now){
    const TxCheckPacket *last=&txcheck.packets[(txcheck.packet_next-1u)%TXCHECK_PACKETS];
    (void)snprintf(line,size,"B5 TXCHK tick=%lu bytes=%lu packets=%lu short=%lu txe_to=%lu gap_ms=%lu reentry=%lu ack_gap_ms=%lu req=%u wr=%u\r\n",
        (unsigned long)now,(unsigned long)txcheck.bytes,(unsigned long)txcheck.count,
        (unsigned long)txcheck.short_write,(unsigned long)txcheck.txe_timeout,
        (unsigned long)txcheck.gap,(unsigned long)txcheck.reentry,(unsigned long)txcheck.ack_gap,
        txcheck.packet_next?last->required:0u,txcheck.packet_next?last->written:0u);
}

void platform_txcheck_report(uint32_t now){
    char line[224];
    txcheck_format(line,sizeof line,now);
    console(line);
}

static void txcheck_exit(void){
    if(!txcheck.packet_next)return;
    const uint32_t now=g_uptime_ms;
    const uint32_t packet_end=txcheck.packet_next,ack_end=txcheck.ack_next;
    uint32_t first_packet=packet_end>TXCHECK_PACKETS?packet_end-TXCHECK_PACKETS:0;
    uint32_t first_ack=ack_end>TXCHECK_ACKS?ack_end-TXCHECK_ACKS:0;
    while(first_ack<ack_end && now-txcheck.acks[first_ack%TXCHECK_ACKS].at>TXCHECK_HISTORY_MS)first_ack++;
    char line[288];
    txcheck_format(line,sizeof line,now);
    console(line);
    (void)snprintf(line,sizeof line,"B5 TXEXIT tick=%lu packet_n=%lu ack_n=%lu ack_overwritten=%lu\r\n",
        (unsigned long)now,(unsigned long)(packet_end-first_packet),(unsigned long)(ack_end-first_ack),
        (unsigned long)(ack_end>TXCHECK_ACKS?ack_end-TXCHECK_ACKS:0));
    console(line);
    if(txcheck.reentry){
        (void)snprintf(line,sizeof line,"B5 TXREENTRY at=%lu outer_stream=%u outer_seq=%lu inner_stream=%u inner_seq=%lu poll=%u\r\n",
            (unsigned long)txcheck.reentry_at,txcheck.reentry_outer_stream,(unsigned long)txcheck.reentry_outer_seq,
            txcheck.reentry_inner_stream,(unsigned long)txcheck.reentry_inner_seq,txcheck.reentry_poll);
        console(line);
    }
    for(uint32_t i=first_packet;i<packet_end;i++){
        const TxCheckPacket *p=&txcheck.packets[i%TXCHECK_PACKETS];
        (void)snprintf(line,sizeof line,"B5 TXPKT at=%lu type=%u stream=%u seq=%lu req=%u wr=%u dur_ms=%lu gap_ms=%lu\r\n",
            (unsigned long)p->at,p->type,p->stream,(unsigned long)p->seq,p->required,p->written,
            (unsigned long)p->duration,(unsigned long)p->gap);
        console(line);
    }
    /* at/id/写完到确认/相邻确认间隔。保留退出前 16 s，供主机按遗嘱时刻裁切。 */
    for(uint32_t i=first_ack;i<ack_end;){
        size_t used=(size_t)snprintf(line,sizeof line,"B5 TXACK rows=");
        for(unsigned j=0;j<6 && i<ack_end;j++,i++){
            const TxCheckAck *a=&txcheck.acks[i%TXCHECK_ACKS];
            used+=(size_t)snprintf(line+used,sizeof line-used,"%s%lu/%u/%lu/%lu",j?",":"",
                (unsigned long)a->at,a->id,(unsigned long)a->delay,(unsigned long)a->interval);
        }
        (void)snprintf(line+used,sizeof line-used,"\r\n");
        console(line);
    }
}
