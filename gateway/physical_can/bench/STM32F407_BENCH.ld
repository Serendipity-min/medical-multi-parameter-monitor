/* H2只准占用前64KiB（sector0..3），sector7和原配置宏所指sector11均不参与链接。 */
ENTRY(Reset_Handler)
MEMORY {
  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 64K
  RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 128K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS {
  .isr_vector : { . = ALIGN(4); KEEP(*(.isr_vector)) . = ALIGN(4); } > FLASH
  .text : { . = ALIGN(4); *(.text*) *(.rodata*) . = ALIGN(4); _etext = .; } > FLASH
  .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > FLASH
  .ARM : { __exidx_start = .; *(.ARM.exidx*) __exidx_end = .; } > FLASH
  _sidata = LOADADDR(.data);
  .data : { . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } > RAM AT > FLASH
  .bss (NOLOAD) : { . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .; } > RAM
  end = .; _end = .;
  /* 与原候选相同的24KiB堆/8KiB栈预算；链接超RAM时必须失败。 */
  ._user_heap_stack (NOLOAD) : { . = ALIGN(8); _heap_start = .; . += 0x6000; _heap_end = .; . += 0x2000; . = ALIGN(8); } > RAM
  /DISCARD/ : { libgcc.a ( * ) }
}
