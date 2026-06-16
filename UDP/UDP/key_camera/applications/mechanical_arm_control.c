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
 * 此处是控制机械臂移动的代码。
 * 代码参考了 https://github.com/alangandy/Max-Arm/tree/9279e756ba92d422660dbc7cebca8d41bcc8476d/6.%20Secondary%20Development/Arduino%20Developmemt/Sensor-extension%20Game/Lesson%2010%20Light%20Detection%20and%20Placement/Program%20File/LightSensor_put
 *
 */

#include <math.h>
#include "servo.h"
#include "os_layer.h"

#define M_PI 3.14159265358979323846

#define L0      84.4    // 疑似底座高度
#define L1      8.14
#define L2      128.4   // 疑似纵向连杆高度
#define L3      138.0
#define L4      16.

float L2_SQUARE = L2 * L2;
float L3_SQUARE = L3 * L3;
float DOUBLE_PI = M_PI * 2.0;

float ORIGIN[3] = { 0, -(L1 + L3 + L4), (L0 + L2) };
float positions[3];

static float degrees(float radians)
{
    return radians * (180.0f / M_PI); // 将弧度转换为度
}

//求逆解
static float* inverse(float pos[3], float* ang)
{
    float x = -pos[0];
    float y = pos[1];
    float z = pos[2];
    float theta1 = 0.0;
    if (x == 0.0)
    {
        if (y >= 0.0)
            theta1 = M_PI / 2.0;
        else
            theta1 = M_PI / 2.0 * 3.0;
    }
    else
    {
        if (y == 0.0)
        {
            if (x > 0.0)
                theta1 = 0.0;
            else
                theta1 = M_PI;
        }
        else
        {
            if (x < 0.0)
                theta1 = atan(y / x) + M_PI;
            else
                theta1 = atan(y / x) + DOUBLE_PI;
        }
    }
    float r = sqrt(x * x + y * y) - L1 - L4; //旋转半径
    z = z - L0;
    if (sqrt(r * r + z * z) > (L2 + L3))
    {
//        Serial.print("r: ");
//        Serial.println(r);
//        Serial.print(L2);
//        Serial.println(L3);
    }
    float alpha = atan(z / r);
    //余弦定理求各关节夹角
    float beta = acos((L2_SQUARE + L3_SQUARE - (r * r + z * z)) / (2.0 * L2 * L3));
    float gamma = acos((L2_SQUARE + (r * r + z * z - L3_SQUARE)) / (2.0 * L2 * sqrt(r * r + z * z)));
    float theta2 = M_PI - (alpha + gamma);
    float theta3 = M_PI - (alpha + beta + gamma);
    //根据需要将角度进行一下偏转，这里将底盘旋转的起始处定为-120度，将坐标系旋转
    float angles = degrees(theta1);
    if (angles <= 30.0)
        angles += 360.0;
    float angle1 = angles - 150.0;
    float angle2 = degrees(theta2);
    float angle3 = degrees(theta3);
    ang[0] = angle1;
    ang[1] = angle2;
    ang[2] = angle3;
    return ang;
}

//角度转脉冲
static float* deg_to_pulse(float ang[3], float* pul)
{
    for (int i = 0; i < 3; i++)
    {
        if (ang[i] < 0.0 | ang[i] > 240.0)
        {
//            Serial.print("Invalid angle:");
//            Serial.println(ang[i]);
        }
    }
    float pulse1 = ang[0] * 1000.0 / 240.0;
    float pulse2 = (ang[1] - 210.0) * 1000.0 / -240.0;
    float pulse3 = (ang[2] + 120.0) * 1000.0 / 240.0;
    pul[0] = pulse1;
    pul[1] = pulse2;
    pul[2] = pulse3;
    return pul;
}

int set_position(BusServo* servo, float pos[3], int duration)
{
    float x = pos[0];
    float y = pos[1];
    float z = pos[2];
    if (z > 255)
        z = 255;
    if (sqrt(x * x + y * y) < 50)
        return 0;
    float angles[3];
    inverse(pos, angles);
    rt_kprintf("angle:x(%d),y(%d),z(%d) ", (int) angles[0], (int) angles[1], (int) angles[2]);
    float pul[3];
    deg_to_pulse(angles, pul);
    rt_kprintf("; pluse:x(%d),y(%d),z(%d)\n  ", (int) pul[0], (int) pul[1], (int) pul[2]);
    for (int i = 0; i < 3; i++)
    {
        positions[i] = pul[i];
        servo->move(servo, i + 1, pul[i], duration);
        ol_delay(2);
    }
    // 等待指令完成
    ol_delay(duration);
    return 1;
}

int go_home(BusServo* servo, int duration)
{
    return set_position(servo, ORIGIN, duration);
}
