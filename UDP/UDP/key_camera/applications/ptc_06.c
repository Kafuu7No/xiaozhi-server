/*
 * Copyright (c) 2006-2021, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-04-05     MICRODYSSEY       the first version
 */
/*
 * 根据ptc-06摄像头编写的实现
 */
#include "ptc_06.h"

/**
 * 判断接收的数据头部是否符号规定头部
 * @param read_buf 接收到的数据
 * @param buf_len 接收到的数据字节长度
 * @param header 期望的头部数据
 * @param header_len 期望头部数据长度
 * @return 头部不一致返回1，一致返回0
 */
static int not_right_header(uint8_t* recv_buf, size_t buf_len, uint8_t header[], size_t header_len)
{
    int i = 0;
    for (i = 0; i < buf_len && i < header_len; i++)
    {
        if (recv_buf[i] != header[i])
        {
            break;
        }
    }
    if (i == header_len)
    {
        return 0;
    }
    else
    {
        return 1;
    }
}
/**
 * 由于复位时返回的版本信息需要在下一次的消息体中才会返回。为了避免影响其他指令的执行，这里提前使用一个无意义的命令清除版本信息。
 * @param self 封装对象
 * @return 成功返回0，失败返回非0
 */
int reset_version_clear(struct PTC06 *self)
{
    uint8_t cmd_buf[] = { 0x56, 0x00, 0x36, 0x01, 0x03 };
    if (self->write(cmd_buf, 5) != 5)
    {
        return 1;
    }
    uint8_t* reader_buf = NULL;
    size_t size = self->read(&reader_buf, READ_ALLOC);
    self->free(reader_buf);
    return 0;
}
// 下面是设备指令封装，详情参考PTC06文档。
int reset(struct PTC06 *self)
{
    uint8_t cmd_buf[4] = { 0x56, 0x00, 0x26, 0x00 };
    uint8_t right_header[] = { 0x76, 0x00, 0x26, 0x00 };
    if (self->write(cmd_buf, 4) != 4)
    {
        return 1;
    }
    ol_delay(500);    // reset的返回体是多段的，需要等待一下，避免接收不完全。

    uint8_t* reader_buf = NULL;
    size_t size = self->read(&reader_buf, READ_ALLOC);

    int ret = not_right_header(reader_buf, size, right_header, 4);
    self->free(reader_buf);
    return ret;
}

int take_photo(struct PTC06 *self)
{
    uint8_t cmd_buf[5] = { 0x56, 0x00, 0x36, 0x01, 0x00 };
    uint8_t right_header[] = { 0x76, 0x00, 0x36, 0x00, 0x00 };
    if (self->write(cmd_buf, 5) != 5)
    {
        return 1;
    }
    uint8_t* reader_buf = NULL;
    size_t size = self->read(&reader_buf, READ_ALLOC);

    int ret = not_right_header(reader_buf, size, right_header, 5);

    self->free(reader_buf);
    return ret;
}

int get_photo_size(struct PTC06 *self, uint16_t *photo_size)
{
    uint8_t cmd_buf[] = { 0x56, 0x00, 0x34, 0x01, 0x00 };
    uint8_t right_header[] = { 0x76, 0x00, 0x34, 0x00, 0x04, 0x00, 0x00 };
    if (self->write(cmd_buf, 5) != 5)
    {
        return 1;
    }
    uint8_t* reader_buf = NULL;
    size_t size = self->read(&reader_buf, READ_ALLOC);

    if (not_right_header(reader_buf, size, right_header, sizeof(right_header) / sizeof(uint8_t)))
    {
        self->free(reader_buf);
        return 1;
    }
    *photo_size = 0;
    *photo_size |= reader_buf[7] << 8;
    *photo_size |= reader_buf[8];

    self->free(reader_buf);
    return 0;
}

int get_photo_binary(struct PTC06 *self, uint16_t photo_size, uint16_t frag_size)
{
    OL_ASSERT(frag_size % 8 == 0, "frag_size must be multiple of 8.\n");
    uint8_t right_header[] = { 0x76, 0x00, 0x32, 0x00, 0x00 };
    uint8_t cmd_buf[] = { 0x56, 0x00, 0x32, 0x0c, 0x00, 0x0a, 0, 0, 0x00, 0x00, // 图片数据起始地址
            0, 0, ((uint8_t) (photo_size >> 8)), ((uint8_t) photo_size), // 本次读取长度
            0x00, 0xff // 结尾
            };
    int s, l;
    int err_count = 0;

    int part_size = frag_size < photo_size ? frag_size : photo_size;
    uint8_t * buf = NULL;
    ol_printf("data = [");
    for (int i = 0; i < (photo_size / part_size) + 1; i++)
    {
        s = i * part_size;
        l = part_size;
        if (s >= photo_size)
        {
            break;
        }
        if (s + l >= photo_size)
        {
            l = photo_size - s;
        }
        cmd_buf[8] = (uint8_t) (s >> 8);
        cmd_buf[9] = (uint8_t) s;
        cmd_buf[12] = (uint8_t) (l >> 8);
        cmd_buf[13] = (uint8_t) l;
        if (self->write(cmd_buf, sizeof(cmd_buf) / sizeof(uint8_t)) != sizeof(cmd_buf) / sizeof(uint8_t))
        {
            return 1;
        }
        size_t size = self->read(&buf, READ_ALLOC);
        // 读取到头部信息
        if (not_right_header(buf, size, right_header, 5)
                || not_right_header(&buf[5 + l], size - 5 - l, right_header, 5))
        {
            i -= 1;
            self->free(buf);
            buf = NULL;
            err_count++;
            if (err_count > 10)
            {
                return 1;
            }
            continue;
        }
        err_count = 0;

        for (int j = s; j < s + l; j++)
        {
            if (j == 0)
            {
                ol_printf("%02x", buf[j - s + 5]);
            }
            else
            {
                ol_printf(",%02x", buf[j - s + 5]);
            }
        }
        ol_printf("\n");

        self->free(buf);
        buf = NULL;
    }
    ol_printf("]\n");

    return 0;
}

int get_photo_binary_with_cb(struct PTC06 *self, uint16_t photo_size, uint16_t frag_size,
        int (*frag_handle)(uint8_t*, uint16_t), int (*end_cb)(void))
{
    OL_ASSERT(frag_size % 8 == 0, "frag_size must be multiple of 8.\n");
    uint8_t right_header[] = { 0x76, 0x00, 0x32, 0x00, 0x00 };
    uint8_t cmd_buf[] = { 0x56, 0x00, 0x32, 0x0c, 0x00, 0x0a, 0, 0, 0x00, 0x00, // 图片数据起始地址
            0, 0, ((uint8_t) (photo_size >> 8)), ((uint8_t) photo_size), // 本次读取长度
            0x00, 0xff // 结尾
            };
    int s, l;
    int err_count = 0;

    int part_size = frag_size < photo_size ? frag_size : photo_size;
    uint8_t * buf = NULL;
    for (int i = 0; i < (photo_size / part_size) + 1; i++)
    {
        s = i * part_size;
        l = part_size;
        if (s >= photo_size)
        {
            break;
        }
        if (s + l >= photo_size)
        {
            l = photo_size - s;
        }
        cmd_buf[8] = (uint8_t) (s >> 8);
        cmd_buf[9] = (uint8_t) s;
        cmd_buf[12] = (uint8_t) (l >> 8);
        cmd_buf[13] = (uint8_t) l;
        if (self->write(cmd_buf, sizeof(cmd_buf) / sizeof(uint8_t)) != sizeof(cmd_buf) / sizeof(uint8_t))
        {
            return 1;
        }
        size_t size = self->read(&buf, READ_ALLOC);
        // 读取到头部信息
        if (not_right_header(buf, size, right_header, 5)
                || not_right_header(&buf[5 + l], size - 5 - l, right_header, 5))
        {
            i -= 1;
            self->free(buf);
            buf = NULL;
            err_count++;
            if (err_count > 10)
            {
                return 1;
            }
            continue;
        }
        err_count = 0;

        if (frag_handle(buf + 5, l))
        {
            // fail to handle a frag, so give up continue receive remain frag.
            return 1;
        }

        self->free(buf);
        buf = NULL;
    }
    if (end_cb())
    {
        // fail to finish.
        return 1;
    }

    return 0;
}
int clear_photo_cache(struct PTC06 *self)
{
    uint8_t cmd_buf[] = { 0x56, 0x00, 0x36, 0x01, 0x03 };
    uint8_t right_header[] = { 0x76, 0x00, 0x36, 0x00, 0x00 };
    if (self->write(cmd_buf, 5) != 5)
    {
        return 1;
    }
    uint8_t* reader_buf = NULL;
    size_t size = self->read(&reader_buf, READ_ALLOC);

    int ret = not_right_header(reader_buf, size, right_header, sizeof(right_header) / sizeof(uint8_t));

    self->free(reader_buf);
    return ret;
}

void init_ptc06(PTC06* camera, WRITE_FUN write, READ_FUN read, READ_BUF_FREE_FUN free)
{
    OL_ASSERT(write, "write ptr must not be NULL");
    OL_ASSERT(read, "read ptr must not be NULL");
    OL_ASSERT(free, "free ptr must not be NULL");
    camera->write = write;
    camera->read = read;
    camera->free = free;
    // init ops function ptr
    camera->reset = reset;
    camera->take_photo = take_photo;
    camera->get_photo_size = get_photo_size;
    camera->clear_photo_cache = clear_photo_cache;
    camera->get_photo_binary = get_photo_binary;
}

struct PTC06 create_ptc06(WRITE_FUN write, READ_FUN read, READ_BUF_FREE_FUN free)
{
    PTC06 camera;
    init_ptc06(&camera, write, read, free);
    return camera;
}
