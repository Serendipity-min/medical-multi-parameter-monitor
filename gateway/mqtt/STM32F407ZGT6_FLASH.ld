/* STM32F407ZGT6：1 MiB Flash，常规 SRAM 使用前 128 KiB。 */
ENTRY(Reset_Handler)

MEMORY
{
  FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 896K
  RAM (xrw)   : ORIGIN = 0x20000000, LENGTH = 128K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
  .isr_vector :
  {
    . = ALIGN(4);
    KEEP(*(.isr_vector))
    . = ALIGN(4);
  } > FLASH

  .text :
  {
    . = ALIGN(4);
    *(.text)
    *(.text*)
    *(.rodata)
    *(.rodata*)
    . = ALIGN(4);
    _etext = .;
  } > FLASH

  .ARM.extab :
  {
    *(.ARM.extab* .gnu.linkonce.armextab.*)
  } > FLASH

  .ARM :
  {
    __exidx_start = .;
    *(.ARM.exidx*)
    __exidx_end = .;
  } > FLASH

  _sidata = LOADADDR(.data);
  .data :
  {
    . = ALIGN(4);
    _sdata = .;
    *(.data)
    *(.data*)
    . = ALIGN(4);
    _edata = .;
  } > RAM AT > FLASH

  .bss (NOLOAD) :
  {
    . = ALIGN(4);
    _sbss = .;
    *(.bss)
    *(.bss*)
    *(COMMON)
    . = ALIGN(4);
    _ebss = .;
  } > RAM

  /* CANopenNode 仅在初始化/节点通信复位时分配；堆上限由 heap.c 强制执行。 */
  end = .;
  _end = .;

  ._user_heap_stack (NOLOAD) :
  {
    . = ALIGN(8);
    _heap_start = .;
    . = . + 0x6000;
    _heap_end = .;
    . = . + 0x2000;
    . = ALIGN(8);
  } > RAM

  /DISCARD/ : { libgcc.a ( * ) }
}
