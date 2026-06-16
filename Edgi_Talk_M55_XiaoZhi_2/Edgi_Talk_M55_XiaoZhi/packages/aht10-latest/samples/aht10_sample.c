/*
 * Copyright (c) 2006-2024, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2024-07-23     Wangyuqiang  the first version
 */

#include <rtthread.h>
#include <rtdevice.h>
#include <finsh.h>

#include "aht10.h"
#include <rtconfig.h>

/* Forward declaration to avoid package include path dependency. */
extern void xiaozhi_ui_set_env_result(float temp, float humi);

#ifndef PKG_AHT10_I2C_BUS_NAME
#define PKG_AHT10_I2C_BUS_NAME "i2c1"
#endif

#define DBG_TAG "aht10"
#define DBG_LVL DBG_LOG
#include <rtdbg.h>

#if defined(PKG_AHT10_USING_SENSOR_V2)
#include "sensor_asair_aht10.h"
#endif

static void aht10_entry(void *parameter)
{
    aht10_device_t dev = RT_NULL;
    const char *bus_name = PKG_AHT10_I2C_BUS_NAME;
    int invalid_count = 0;

    while (1)
    {
        if (dev == RT_NULL)
        {
            dev = aht10_init(bus_name);
            if (dev == RT_NULL)
            {
                LOG_W("aht10 init failed on %s, retry in 2s", bus_name);
                rt_thread_mdelay(2000);
                continue;
            }
            invalid_count = 0;
            LOG_I("aht10 started on %s", bus_name);
        }

        float temperature = aht10_read_temperature(dev);
        float humidity = aht10_read_humidity(dev);

        if ((temperature > -40.0f && temperature < 125.0f) &&
            (humidity >= 0.0f && humidity <= 100.0f))
        {
            invalid_count = 0;
            xiaozhi_ui_set_env_result(temperature, humidity);
        }
        else
        {
            invalid_count++;
            LOG_W("aht10 invalid data on %s: T=%.2f H=%.2f", bus_name, temperature, humidity);
            if (invalid_count >= 3)
            {
                LOG_W("aht10 reinit after %d invalid reads", invalid_count);
                aht10_deinit(dev);
                dev = RT_NULL;
                invalid_count = 0;
                rt_thread_mdelay(500);
                continue;
            }
        }

        rt_thread_mdelay(1500);
    }
}

int aht10_thread_port(void)
{
    rt_thread_t res = rt_thread_create("aht10", aht10_entry, RT_NULL, 1024, 20, 50);
    if(res == RT_NULL)
    {
        LOG_E("aht10 thread create failed!");
        return -RT_ERROR;
    }

    rt_thread_startup(res);

    return RT_EOK;
}
INIT_DEVICE_EXPORT(aht10_thread_port);

#ifdef RT_USING_FINSH
static int i2c_scan(int argc, char **argv)
{
    const char *bus_name = "i2c1";
    if (argc >= 2 && argv[1] && argv[1][0] != '\0')
        bus_name = argv[1];

    struct rt_i2c_bus_device *bus = (struct rt_i2c_bus_device *)rt_device_find(bus_name);
    if (!bus)
    {
        rt_kprintf("i2c_scan: bus '%s' not found\n", bus_name);
        return -RT_ERROR;
    }

    rt_kprintf("Scanning I2C bus %s...\n", bus_name);
    int found = 0;
    for (rt_uint16_t addr = 0x03; addr <= 0x77; addr++)
    {
        rt_uint8_t dummy = 0;
        struct rt_i2c_msg msg;
        msg.addr  = addr;
        msg.flags = RT_I2C_WR;
        msg.buf   = &dummy;
        msg.len   = 0; /* address-only probe */

        if (rt_i2c_transfer(bus, &msg, 1) == 1)
        {
            rt_kprintf("  found: 0x%02X\n", addr);
            found++;
        }
    }

    if (!found)
        rt_kprintf("  no device found on %s\n", bus_name);
    else
        rt_kprintf("scan done, %d device(s) found\n", found);

    return RT_EOK;
}
MSH_CMD_EXPORT(i2c_scan, Scan i2c bus usage i2c_scan [i2c1|i2c0]);
#endif
