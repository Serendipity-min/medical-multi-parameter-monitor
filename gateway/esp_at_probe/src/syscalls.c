#include <sys/stat.h>
#include <sys/types.h>

/*
 * 控制台只通过 USART 发送数据，不使用半主机、文件系统或标准输入输出句柄。
 * 显式拒绝 newlib 的文件 I/O 请求，避免链接器使用“未实现但继续运行”的默认桩。
 */
int _close(int file)
{
  (void)file;
  return -1;
}

int _fstat(int file, struct stat *st)
{
  (void)file;
  st->st_mode = S_IFCHR;
  return 0;
}

int _isatty(int file)
{
  (void)file;
  return 1;
}

int _lseek(int file, int pointer, int direction)
{
  (void)file;
  (void)pointer;
  (void)direction;
  return -1;
}

int _read(int file, char *buffer, int length)
{
  (void)file;
  (void)buffer;
  (void)length;
  return -1;
}

int _write(int file, const char *buffer, int length)
{
  (void)file;
  (void)buffer;
  (void)length;
  return -1;
}
