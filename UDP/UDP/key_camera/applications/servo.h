/*
 * Copyright (c) 2006-2021, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-04-05     MICRODYSSEY       the first version
 */
#ifndef __SERVO_H__
#define __SERVO_H__

#include "os_layer.h"

typedef struct BusServo
{
    uint8_t *buf;   // 输出缓冲区
    void (*writer)(void *buf, uint16_t len);    // 外部提供的输出函数
    void (*move)(struct BusServo *self, uint8_t id, uint16_t pulse, uint16_t duration); // 内部提供实现，控制步进电机旋转
} BusServo;
typedef struct PWMServo
{
    int16_t cur_pul;
    void (*set)(uint32_t period, uint32_t high_duration); // 外部提供的设置pwm占空比的函数
    void (*move)(struct PWMServo* self, uint8_t angle, uint16_t duration); // 内部提供实现，控制电机旋转角度
} PWMServo;

struct BusServo create_bus_servo(void (*writer)(void *buf, uint16_t len), uint8_t *buf);
void init_bus_servo(struct BusServo *servo, void (*writer)(void *buf, uint16_t len), uint8_t *buf);

struct PWMServo create_pwm_servo(void (*set)(uint32_t period, uint32_t high_duration));
void init_pwm_servo(struct PWMServo* servo, void (*set)(uint32_t, uint32_t));
#endif
