/*
 * Copyright (c) 2006-2021, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-04-05     MICRODYSSEY       the first version
 */
#ifndef __PTC_06_H__
#define __PTC_06_H__

#include "os_layer.h"

/**
 * 指令写入的函数，由外部提供
 * @param buf 写入指令的字节指针
 * @param len 字节数
 * @return 实际输出的字节数
 */
typedef int (*WRITE_FUN)(uint8_t *buf, uint16_t len);

#define READ_ALLOC -1   /**< 表示read需要自己申请接受缓存区，并由调用者调用free释放 */
#define READ_ABORT -2   /**< 表示此处的read 不关心数据，只需要抛弃读取的数据就行 */
/**
 * 返回数据读取函数，由外部实现。
 * 如果len为READ_ALLOC，表示该缓存区由read函数内部申请，并配合使用free释放。
 * 否则，表示缓冲区已经申请，len表示缓存区最大大小。
 * @param buf 接收缓存区指针的指针
 * @param len 缓冲区最大大小，如果为READ_ALLOC表示未申请
 * @return 实际收到的数据的字节数
 */
typedef uint32_t (*READ_FUN)(uint8_t **buf_ptr, int32_t len);
/**
 * 空间释放函数。
 * 当接受缓冲区由read函数申请时，需要使用该函数接口进行空间释放。
 *
 * 返回数据空间释放函数，由外部实现。
 *  因为空间可能由read函数申请，不一定和ol_free是匹配，此时需要使用提供read函数的开发者提供对应的free函数。
 *  不能直接使用ol_free。
 * @param ptr 需要释放的空间地址
 */
typedef void (*READ_BUF_FREE_FUN)(void* ptr);

typedef struct PTC06
{
    WRITE_FUN write;
    READ_FUN read;
    READ_BUF_FREE_FUN free;
    /**
     * 软复位，开机延迟2.5s后执行。
     * @param self
     * @return 成功返回0，失败返回非0
     */
    int (*reset)(struct PTC06 *self);
    /**
     * 执行拍照。每次读取照片前需要执行。
     * @param self
     * @return 成功返回0，失败返回非0
     */
    int (*take_photo)(struct PTC06 *self);
    /**
     * 获取照片数据的大小。
     * @param self
     * @param photo_size 2字节数据的指针，成功将会写入照片的字节数。
     * @return 成功返回0，失败返回非0
     */
    int (*get_photo_size)(struct PTC06 *self, uint16_t *photo_size);

    /**
     * 清除照片缓存，每次重新拍照前，需要执行。
     * @param self
     * @return 成功返回0，失败返回非0
     */
    int (*clear_photo_cache)(struct PTC06 *self);
    /**
     * 获取照片的二进制数据
     * @param self
     * @param photo_size 照片数据大小
     * @param frag_size 每次读取照片数据的最大大小，photo_size大于frag_size就会分多次读取，否则一次性读取。
     * 注意此参数必须为8的倍数，且frag_size + 10 不超过uart接收缓冲区大小。
     * @return 成功返回0，失败返回非0
     */
    int (*get_photo_binary)(struct PTC06 *self, uint16_t photo_size, uint16_t frag_size);
} PTC06;

void init_ptc06(struct PTC06 *camera, WRITE_FUN write, READ_FUN read, READ_BUF_FREE_FUN free);
struct PTC06 create_ptc06(WRITE_FUN write, READ_FUN read, READ_BUF_FREE_FUN free);
int get_photo_binary_with_cb(struct PTC06 *self, uint16_t photo_size, uint16_t frag_size,
        int (*frag_handle)(uint8_t*, uint16_t), int (*end_cb)(void));

#endif
