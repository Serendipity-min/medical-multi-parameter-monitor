#ifndef PF6_DIAG_H
#define PF6_DIAG_H
#include <stdbool.h>
#include <stdint.h>

typedef struct { unsigned length; bool valid,used; } Pf6Command;
typedef struct { unsigned length; bool discard; } Pf6Reply;

static inline bool pf6_command_byte(Pf6Command *s,int byte){
    static const char command[]="PF6\r";
    if(s->used)return false;
    if(byte=='\n'){
        s->used=s->valid && (s->length==3u || s->length==4u);
        s->length=0;s->valid=true;
        return s->used;
    }
    if(s->length>=sizeof command-1 || byte!=command[s->length])s->valid=false;
    else s->length++;
    return false;
}

static inline bool pf6_reply_byte(Pf6Reply *s,int byte,const char *line,unsigned size){
    if(byte<0){s->discard=true;return false;}
    if(byte=='\n'){
        bool match=!s->discard && s->length==size-1u;
        *s=(Pf6Reply){0};
        return match;
    }
    if(s->length>=size-1u || byte!=line[s->length])s->discard=true;
    else s->length++;
    return false;
}
#endif
