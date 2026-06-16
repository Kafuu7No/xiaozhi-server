/*
 * Copyright (c) 2006-2021, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-04-05     MICRODYSSEY       the first version
 */
/**
 * 提供一些接口封装。
 * 避免电机、摄像头的代码难以迁移。
 */
#ifndef __OS_LAYER_H__
#define __OS_LAYER_H__

// 提供 uint8_t, uint16_t, int32_t等类型，可根据需要自行修改。
#include <stddef.h>
#include <stdint.h>

// 下面是提供的封装
/**
 * delay 函数，是占据cpu还是不占用cpu的形式，未定。由实现决定。
 * @param ms 毫秒
 */
extern void ol_delay(uint32_t ms);
/**
 * 发生异常，完全中断程序执行。
 */
extern void ol_panic(const char *msg);
/**
 * 动态空间申请
 * @param 空间字节大小
 */
extern void* ol_malloc(size_t);
/**
 * 释放动态空间
 * @param 指向参数
 */
extern void ol_free(void*);

// 不定数量参数的函数，不好进行wrap，就使用指针形式了。
extern void (*ol_printf)(const char *fmt, ...);

#define OL_ASSERT(expr,msg) do{\
    if(!(expr)) {             \
        ol_panic(msg);      \
    }                       \
}while(0);

#endif
