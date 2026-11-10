/* 神舟号 V2.0：PF6/GBC_KEY 为低有效 RST，PC0/GBC_LED 读取 GPIO0 启动绑带。 */
int platform_esp_hard_reset(void){
    RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOC|RCC_AHB1Periph_GPIOF,ENABLE);
    GPIO_InitTypeDef pin={0};
    pin.GPIO_Pin=GPIO_Pin_0;pin.GPIO_Mode=GPIO_Mode_IN;pin.GPIO_PuPd=GPIO_PuPd_UP;
    GPIO_Init(GPIOC,&pin);
    if(!GPIO_ReadInputDataBit(GPIOC,GPIO_Pin_0))return 0;

    /* 先设开漏和释放态，再切输出，避免共享网出现推挽电平。 */
    GPIOF->OTYPER|=GPIO_Pin_6;
    GPIO_SetBits(GPIOF,GPIO_Pin_6);
    pin.GPIO_Pin=GPIO_Pin_6;pin.GPIO_Mode=GPIO_Mode_OUT;pin.GPIO_OType=GPIO_OType_OD;
    GPIO_Init(GPIOF,&pin);
    if(!GPIO_ReadInputDataBit(GPIOC,GPIO_Pin_0))return 0;
    GPIO_ResetBits(GPIOF,GPIO_Pin_6);
    uint32_t began=g_uptime_ms;
    do{
        platform_poll();
        /* 按住复位时若绑带变低，保持 RST，避免释放后进入 ROM。 */
        if(!GPIO_ReadInputDataBit(GPIOC,GPIO_Pin_0))return -1;
    }while((uint32_t)(g_uptime_ms-began)<21u);
    GPIO_SetBits(GPIOF,GPIO_Pin_6);
    if(!GPIO_ReadInputDataBit(GPIOC,GPIO_Pin_0)){
        GPIO_ResetBits(GPIOF,GPIO_Pin_6);
        return -1;
    }
    return 1;
}
