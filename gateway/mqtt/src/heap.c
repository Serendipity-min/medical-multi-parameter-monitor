/* CANopenNode 初始化使用 calloc；堆有固定上限，绝不越过预留主栈。 */
#include <stddef.h>
#include <errno.h>
extern char _heap_start, _heap_end;

/* newlib 堆只能增长到链接脚本保留区末尾；不足时返回 ENOMEM，不能挤占栈。 */
void *_sbrk(ptrdiff_t increment)
{
    static char *current;
    if (!current)
        current = &_heap_start;
    if (increment < 0 || increment > (&_heap_end - current))
    {
        errno = ENOMEM;
        return (void *)-1;
    }
    char *previous = current;
    current += increment;
    return previous;
}
