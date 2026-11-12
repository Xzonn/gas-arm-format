.syntax unified
.cpu arm946e-s
.arm
.text
.global entry
.type entry,%function
.macro load_value name, value=1
\name\()_start:
mov  r0,#\value
add r0,r0,#1
.endm
entry:
push {r4,lr}
load_value test, 0x20
ldr r1,[r0,#4]!
mov r2,#'A
mov r3,#' '
mov r4,#1;add r4,r4,#2
1: sub r0,r0,#1 @ keep, comment
bne 1b
pop {r4,pc}
.data
.word 1<<4,2|1
.ascii "x,  y @ # ; //", "quote: \""
.byte 'A, 'B
.altmacro
.macro emit text
.ascii "\text"
.endm
emit <hello,   world>
.noaltmacro
