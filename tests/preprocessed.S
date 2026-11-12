#define TEXT(...) #__VA_ARGS__
#define LABEL(name) name ## _entry
.syntax unified
.cpu arm946e-s
#ifdef THUMB
.thumb
.thumb_func
#else
.arm
#endif
LABEL(test):
movs r0,#1
bx lr
.data
.ascii TEXT(hello,world)
.ascii TEXT(hello;world)
.ascii TEXT(outer(inner,  value))
