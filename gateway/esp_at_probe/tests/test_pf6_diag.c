#include "../src/pf6_diag.h"
#include <assert.h>
#include <stdio.h>

static unsigned commands(Pf6Command *state,const char *text){
    unsigned count=0;
    while(*text)count+=pf6_command_byte(state,(unsigned char)*text++);
    return count;
}

static bool has_line(Pf6Reply *state,const char *text,const char *line,unsigned size){
    while(*text)
        if(pf6_reply_byte(state,(unsigned char)*text++,line,size))return true;
    return false;
}

int main(void){
    Pf6Command s={.valid=true};
    assert(!commands(&s,"START\r\nKEY\nPF6 X\nPF\r6\nxxxPF6\n"));
    assert(!commands(&s,"PF") && commands(&s,"6\r\nPF6\n")==1 && s.used);
    s=(Pf6Command){.valid=true};
    assert(commands(&s,"PF6\n")==1);
    Pf6Reply r={0};
    assert(!has_line(&r,"not ready\r\nready\nready X\r\n","ready\r\n",7));
    assert(!pf6_reply_byte(&r,-1,"ready\r\n",7));
    assert(!has_line(&r,"ready\r\n","ready\r\n",7));
    assert(!has_line(&r,"rea","ready\r\n",7) && has_line(&r,"dy\r\n","ready\r\n",7));
    assert(!has_line(&r,"AT\r\nSEND OK\r\n","OK\r\n",4));
    assert(has_line(&r,"\r\nOK\r\n","OK\r\n",4));
    puts("PASS_AP_EXACT_ONE_SHOT_AND_READY_AT_LINE_BOUNDARIES");
}
