#ifndef B5_PASS_RECOVERY_H
#define B5_PASS_RECOVERY_H
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

enum { PASS_REENTRY_MAX=3, PASS_STABLE_MS=300000 };
#define PASS_RESUME_TAG UINT32_C(0x50414c00)

typedef struct { uint32_t tag, inverse; } PassResume;
typedef struct { unsigned reentries; bool reset_used; } PassRecovery;
typedef struct {
    uint32_t reset_flags,next_at,uart_err0;
    unsigned escape_sent,at_ok,resumed,reentries;
    bool done;
} PassBootDiag;

static inline uint32_t pass_acquire_backoff(uint32_t *next){
    uint32_t delay=*next;
    *next=delay<15000u?delay*2u:30000u;
    return delay;
}

static inline bool pass_boot_diag_due(PassBootDiag *diag,uint32_t now){
    if(diag->done)return false;
    if(now>=60000u){diag->done=true;return false;}
    if(now<diag->next_at)return false;
    diag->next_at=(now/5000u+1u)*5000u;
    return true;
}

static inline void pass_boot_diag_append(char *out,size_t size,const PassBootDiag *diag){
    if(diag->done){(void)snprintf(out,size,"\r\n");return;}
    (void)snprintf(out,size," boot_rst=%lx boot_escape=%u boot_at=%u boot_resume=%u boot_reentries=%u boot_uart_err0=%lu\r\n",
        (unsigned long)diag->reset_flags,diag->escape_sent,diag->at_ok,diag->resumed,diag->reentries,
        (unsigned long)diag->uart_err0);
}

static inline bool pass_resume_take(PassRecovery *state,volatile PassResume *record,bool software_reset){
    uint32_t tag=record->tag,inverse=record->inverse;
    record->tag=0;record->inverse=0;
    if(!software_reset)return true;
    unsigned count=tag&0xffu;
    if((tag&~UINT32_C(0xff))!=PASS_RESUME_TAG || inverse!=~tag || !count || count>PASS_REENTRY_MAX)
        return false;
    *state=(PassRecovery){count,true};
    return true;
}

static inline bool pass_reset_allowed(const PassRecovery *state,bool stopped,bool timed){
    return !stopped && !timed && !state->reset_used && state->reentries<PASS_REENTRY_MAX;
}

static inline bool pass_session_limit(unsigned *reentries){
    if(*reentries<PASS_REENTRY_MAX-1u)return false;
    *reentries=PASS_REENTRY_MAX;
    return true;
}

static inline void pass_resume_save(const PassRecovery *state,volatile PassResume *record){
    uint32_t tag=PASS_RESUME_TAG|(state->reentries+1u);
    record->inverse=~tag;
    record->tag=tag;
}

static inline bool pass_recovery_stable(PassRecovery *state,uint32_t now,uint32_t online_since){
    if(!state->reentries || now-online_since<PASS_STABLE_MS)return false;
    *state=(PassRecovery){0};
    return true;
}
#endif
