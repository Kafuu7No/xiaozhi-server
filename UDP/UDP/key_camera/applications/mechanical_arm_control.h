/*
 * Copyright (c) 2006-2021, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-04-05     MICRODYSSEY       the first version
 */
#ifndef APPLICATIONS_MECHANICAL_ARM_CONTROL_H_
#define APPLICATIONS_MECHANICAL_ARM_CONTROL_H_

#include "servo.h"
int set_position(BusServo* servo, float pos[3], int duration);
int go_home(BusServo* servo, int duration);

#endif /* APPLICATIONS_MECHANICAL_ARM_CONTROL_H_ */
