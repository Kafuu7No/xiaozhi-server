/*
 * Copyright (c) 2006-2021, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-04-05     MICRODYSSEY       the first version
 */
#include <rtthread.h>
#include <os_layer.h>

typedef void (*PRINTF_TYPE)(const char *fmt, ...);
PRINTF_TYPE ol_printf = (PRINTF_TYPE) rt_kprintf;

void ol_delay(uint32_t ms)
{
    rt_thread_mdelay(ms);
}

void ol_panic(const char*msg)
{
    rt_kprintf(msg);
    RT_ASSERT(0);
}

void* ol_malloc(const size_t size)
{
    return rt_malloc(size);
}

void ol_free(void* ptr)
{
    rt_free(ptr);
}
