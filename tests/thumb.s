.syntax unified
.cpu arm946e-s
.thumb
.text
.global thumb_entry
.thumb_func
thumb_entry:
push {r4,lr}
movs r0,#1
adds r0,r0,#2
ldr r1,[r0,#4]
1:subs r0,r0,#1
bne 1b
pop {r4,pc}
