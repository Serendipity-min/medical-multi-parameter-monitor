#ifndef B5_PASS_RECOVERY_H
#define B5_PASS_RECOVERY_H
#include <stdbool.h>
#include <stdint.h>

enum { PASS_REENTRY_MAX=3, PASS_STABLE_MS=300000 };
#define PASS_RESUME_TAG UINT32_C(0x50414c00)

typedef struct { uint32_t tag, inverse; } PassResume;
typedef struct { unsigned reentries; bool reset_used; } PassRecovery;

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
