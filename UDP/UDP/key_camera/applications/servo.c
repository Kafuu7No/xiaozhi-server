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
 * 此处为HTS-35H的总线电机和pwm电机实现了部分的控制协议。
 */
#include "os_layer.h"
#include "servo.h"

/**
 * 部分实现的HTS-35H总线电机的控制协议。
 * 为了简化，此处只实现了一个命令，其他指令，此处未实现。
 */

/**
 * 根据HTS-35H电机的规则计算校验和。
 * @param buf 需要计算的字节数组的指针
 * @param len 字节数组的长度
 * @return
 */
static uint8_t checksum(uint8_t *buf, uint16_t len)
{
    uint8_t ret = 0;
    for (int i = 0; i < len; i++)
    {
        ret += buf[i];
    }
    return ~ret;
}

/**
 * 控制总线步进电机的旋转。
 * @param self 对象封装
 * @param id 电机id
 * @param pulse 电机电平，0~1000
 * @param duration 完成变化的时间，毫秒
 */
void bus_move(struct BusServo *self, uint8_t id, uint16_t pulse, uint16_t duration)
{
    if (pulse > 1000)
    {
        pulse = 1000;
    }
    self->buf[0] = 0x55;
    self->buf[1] = 0x55;
    self->buf[2] = id;
    self->buf[3] = 7;
    self->buf[4] = 1;
    self->buf[5] = (uint8_t) pulse;
    self->buf[6] = (uint8_t) (pulse >> 8);
    self->buf[7] = (uint8_t) duration;
    self->buf[8] = (uint8_t) (duration >> 8);
    self->buf[9] = checksum(&(self->buf[2]), 7);
    self->writer(self->buf, 10);
}

/**
 * 初始化对象
 * @param servo 封装对象指针
 * @param writer  实现了输出的函数, 不能为NULL.
 * @param buf   用于输出的缓冲区指针,不能为NULL.
 */
void init_bus_servo(struct BusServo *servo, void (*writer)(void *buf, uint16_t len), uint8_t *buf)
{

    OL_ASSERT(buf, "buf must not be NULL!\n");

    OL_ASSERT(writer, "writer ptr must not be NULL!\n");

    servo->buf = buf;
    servo->writer = writer;
    servo->move = bus_move;
}

/**
 * 创建封装对象
 * @param writer 实现了输出的函数
 * @param buf 输出缓冲区指针
 * @return 封装对象
 */
struct BusServo create_bus_servo(void (*writer)(void *buf, uint16_t len), uint8_t *buf)
{

    struct BusServo servo;
    init_bus_servo(&servo, writer, buf);
    return servo;
}

/**
 * 下面是为PWM电机实现的控制协议。
 */
// 20ms
#define PERIOD 20*1000
// duration切分的间隔
#define MIN_INTERVAL_MS 10
/**
 * 控制pwm电机旋转角度。
 * @param self 封装对象
 * @param angle 旋转角度，0~180度。
 */
void pwm_move(struct PWMServo* self, uint8_t angle, uint16_t duration)
{
    int pul = angle * 2000 / 180 + 500;
    if (self->cur_pul < 0)
    {
        self->set(PERIOD, pul);
        self->cur_pul = pul;
    }
    else
    {
        int part_pul = (pul - self->cur_pul) / (duration / MIN_INTERVAL_MS);
        int output_pul = self->cur_pul + part_pul;
        while (output_pul < pul)
        {
            self->set(PERIOD, output_pul);
            ol_delay(MIN_INTERVAL_MS);
            output_pul += part_pul;
        }
        if (output_pul != pul)
        {
            self->set(PERIOD, pul);
        }
        self->cur_pul = pul;
    }
}

/**
 * 初始化pwm电机封装对象
 * @param servo 封装对象指针
 * @param set 设置pwm占空比函数，不能为NULL.
 */
void init_pwm_servo(struct PWMServo* servo, void (*set)(uint32_t, uint32_t))
{
    OL_ASSERT(set, "set ptr must not be NULL!");

    servo->set = set;
    servo->move = pwm_move;
    servo->cur_pul = -1;
}

/**
 * 创建pwm电机封装对象
 * @param set 设置pwm占空比函数，不能为NULL。
 * @return 创建的封装对象
 */
struct PWMServo create_pwm_servo(void (*set)(uint32_t, uint32_t))
{
    struct PWMServo servo;
    init_pwm_servo(&servo, set);
    return servo;
}
