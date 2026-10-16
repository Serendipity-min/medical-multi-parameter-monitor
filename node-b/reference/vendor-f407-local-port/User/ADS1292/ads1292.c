//-----------------------------------------------------------------
// 程序描述:
//     ADS1292驱动程序
// 作    者: 凌智电子
// 开始日期: 2018-08-04
// 完成日期: 2018-08-04
// 修改日期:
// 当前版本: V1.0
// 历史版本:
//  - V1.0: (2018-08-04)ADS1292驱动
// 调试工具: 凌智STM32F429+CycloneIV电子系统设计开发板、LZE_ST_LINK2
// 说    明:
//
//-----------------------------------------------------------------

//-----------------------------------------------------------------
// 头文件包含
//-----------------------------------------------------------------
#include "ads1292.h"
#include "spi.h"
#include "delay.h"
//-----------------------------------------------------------------

//-----------------------------------------------------------------
// void ADS1292_Init(void)
//-----------------------------------------------------------------
//
// 函数功能: ADS1292初始化
// 入口参数: 无
// 返 回 值: 无
// 注意事项: 无
//
//-----------------------------------------------------------------
void ADS1292_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct;

  __HAL_RCC_GPIOA_CLK_ENABLE();

  // ADS1292_DRDY -> PE9
//  GPIO_InitStruct.Pin   = GPIO_PIN_9;       // 配置ADS1292_DRDY
//  GPIO_InitStruct.Mode  = GPIO_MODE_INPUT;  // 输入
//  GPIO_InitStruct.Pull  = GPIO_PULLUP;      // 上拉
//  GPIO_InitStruct.Speed = GPIO_SPEED_HIGH; 	// 高速
//  HAL_GPIO_Init(GPIOE, &GPIO_InitStruct);  	// 初始化

  // ADS1292_START -> PA1
  // ADS1292_PWDN  -> PA0
  // ADS1292_CS  	 -> PA2
  GPIO_InitStruct.Pin   = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2;
  GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP; 	// 推挽输出
  GPIO_InitStruct.Pull  = GPIO_PULLUP;         	// 上拉
  GPIO_InitStruct.Speed = GPIO_SPEED_HIGH;    	// 高速
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);     	// 初始化

  SPI5_Init(); // SPI初始化
}

//-----------------------------------------------------------------
// void ADS1292_PowerOnInit(void)
//-----------------------------------------------------------------
//
// 函数功能: ADS1292上电复位
// 入口参数: 无
// 返 回 值: 无
// 注意事项: 无
//
//-----------------------------------------------------------------
void ADS1292_PowerOnInit(void)
{
	u8 device_id;

  ADS1292_START = 0; // 初始化期间不转换，避免中断读数据与SPI配置抢总线
  ADS1292_CS = 1;
  ADS1292_PWDN = 1;

  ADS1292_PWDN = 0; // 进入掉电模式
  delay_ms(10);
  ADS1292_PWDN = 1; // 退出掉电模式
  delay_ms(1000);   // 等待内部基准建立

  ADS1292_CS = 0;   // 软件复位，清掉芯片可能残留的异常状态
  SPI5_Send_Byte(RESET);
  delay_us(10);
  ADS1292_CS = 1;
  delay_ms(10);

  ADS1292_CS = 0;          // wakeup: make sure chip is not stuck in standby
  SPI5_Send_Byte(WAKEUP);
  delay_us(10);
  ADS1292_CS = 1;
  delay_ms(1);

	ADS1292_CS = 0;
  SPI5_Send_Byte(SDATAC); // 发送停止连续读取数据命令
	delay_us(10);
	ADS1292_CS = 1;
	
	// 获取芯片ID
	device_id = ADS1292_Read_Reg(RREG | ID);
	while(device_id != 0x73)
	{
		printf("ERROR ID:%02x\r\n",device_id);
		device_id = ADS1292_Read_Reg(RREG | ID);
		HAL_Delay(1000);
	}
	
	delay_us(10);
  ADS1292_Write_Reg(WREG | CONFIG2,  0XE0); // 使用内部参考电压
  delay_ms(10);                            	// 等待内部参考电压稳定
  ADS1292_Write_Reg(WREG | CONFIG1,  0X01); // 设置转换速率为250SPS
  delay_us(10);
  ADS1292_Write_Reg(WREG | LOFF,     0XF8);	// DC检波, 6uA
  delay_us(10);
  ADS1292_Write_Reg(WREG | CH1SET,   0X60); // 增益12，呼吸通道(恢复原值)
  delay_us(10);
  ADS1292_Write_Reg(WREG | CH2SET,   0X60); // 心电通道增益12(原6), 放大QRS
  delay_us(10);
  ADS1292_Write_Reg(WREG | RLD_SENS, 0xCB); // 关RLD缓冲器: 判别25Hz环路自激实验
  delay_us(10);
  ADS1292_Write_Reg(WREG | LOFF_SENS,0x00); // 关检波电流: DC 6uAx56K=336mV会顶死通道, 接触诊断已完成
  delay_us(10);
	ADS1292_Write_Reg(WREG | LOFF_STAT,0x00);
  delay_us(10);
  ADS1292_Write_Reg(WREG | RESP1,    0xEA); // 开启呼吸检测（ADS1292R特有）
  delay_us(10);
  ADS1292_Write_Reg(WREG | RESP2,    0x03);
  delay_us(10);
  ADS1292_Write_Reg(WREG | GPIO,     0x0C);
  delay_us(10);
}

//-----------------------------------------------------------------
// void ADS1292_Write_Reg(u8 com, u8 data)
//-----------------------------------------------------------------
//
// 函数功能: 对ADS1292的内部寄存器进行写操作
// 入口参数: 无
// 返 回 值: 无
// 注意事项: 无
//
//-----------------------------------------------------------------
void ADS1292_Write_Reg(u8 addr, u8 data)
{
	ADS1292_CS = 0;				// 片选拉低
  SPI5_Send_Byte(addr);	// 包含命令操作码和寄存器地址
  delay_us(10);
  SPI5_Send_Byte(0x00);	// 要读取的寄存器数+1
  delay_us(10);
  SPI5_Send_Byte(data);	// 写入的数据
	delay_us(10);
	ADS1292_CS = 1;				// 片选置高
}

//-----------------------------------------------------------------
// u8 ADS1292_Read_Reg(u8 addr)
//-----------------------------------------------------------------
//
// 函数功能: 对ADS1292的内部寄存器进行读操作
// 入口参数: 无
// 返 回 值: 无
// 注意事项: 无
//
//-----------------------------------------------------------------
u8 ADS1292_Read_Reg(u8 addr)
{
  u8 Rxdata;
	ADS1292_CS = 0;
  SPI5_Send_Byte(addr); 			// 包含命令操作码和寄存器地址
  delay_us(10);
  SPI5_Send_Byte(0x00); 			// 要读取的寄存器数+1
  delay_us(10);
  Rxdata = SPI5_Read_Byte(); 	// 读取的数据
	delay_us(10);
	ADS1292_CS = 1;
  return Rxdata;
}

//-----------------------------------------------------------------
// u8 ADS1292_Read_Data(u8 addr)
//-----------------------------------------------------------------
//
// 函数功能: 读取ADS1292的数据
// 入口参数: 无
// 返 回 值: 无
// 注意事项: 无
//
//-----------------------------------------------------------------
void ADS1292_Read_Data(u8 *data)
{
  u8 i;
	ADS1292_CS = 0;
	delay_us(10);
  SPI5_Send_Byte(RDATAC);		// 发送启动连续读取数据命令
  delay_us(10);
	ADS1292_CS = 1;						
  ADS1292_START = 1; 				// 启动转换
  while (HAL_GPIO_ReadPin(GPIOA, GPIO_PIN_3) == 1);	// 等待DRDY信号拉低
  ADS1292_CS = 0;
  for (i = 0; i < 9; i++)		// 连续读取9个数据
  {
    *data = SPI5_Read_Byte();
    data++;
  }
  ADS1292_START = 0;				// 停止转换
  SPI5_Send_Byte(SDATAC);		// 发送停止连续读取数据命令
	delay_us(10);
	ADS1292_CS = 1;
}

//-----------------------------------------------------------------
// u8 ADS1292_GetLeadOff(void)
//-----------------------------------------------------------------
// 函数功能: 读电极脱落状态寄存器(1=脱落)
//          bit0=IN1P bit1=IN1N bit2=IN2P bit3=IN2N bit4=RLD饱和
// 注意事项: 调用前须关EXTI3防抢SPI; 返回后CS保持低(继续连续读)
//-----------------------------------------------------------------
u8 ADS1292_GetLeadOff(void)
{
  u8 s;
  ADS1292_CS = 0;
  delay_us(10);
  SPI5_Send_Byte(SDATAC);
  delay_us(10);
  ADS1292_CS = 1;
  s = ADS1292_Read_Reg(RREG | LOFF_STAT);
  ADS1292_CS = 0;
  delay_us(10);
  SPI5_Send_Byte(RDATAC);
  delay_us(10);
  return s;
}
//-----------------------------------------------------------------
// End Of File
//-----------------------------------------------------------------
