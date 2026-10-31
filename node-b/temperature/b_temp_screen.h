#ifndef B_TEMP_SCREEN_H
#define B_TEMP_SCREEN_H
#include <stdint.h>
void BTempScreen_Init(void);
void BTempScreen_Refresh(uint32_t now);
int BTempScreen_IsSelected(void);
#endif
