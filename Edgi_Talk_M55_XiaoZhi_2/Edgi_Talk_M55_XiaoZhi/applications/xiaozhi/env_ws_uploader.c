#include "env_ws_uploader.h"
#include "ui/xiaozhi_ui.h"

#include <rtdevice.h>
#include <string.h>

#ifdef RT_USING_I2C
#include <drivers/i2c.h>
#endif

#ifdef PKG_USING_AHT10
#include <aht10.h>
#endif

#define DBG_TAG "xz.env"
#define DBG_LVL DBG_LOG
#include <rtdbg.h>

#ifndef ENV_WS_PERIOD_MS
#define ENV_WS_PERIOD_MS 10000
#endif

#ifndef ENV_AHT20_I2C_BUS_NAME
#ifdef PKG_AHT10_I2C_BUS_NAME
#define ENV_AHT20_I2C_BUS_NAME PKG_AHT10_I2C_BUS_NAME
#else
#define ENV_AHT20_I2C_BUS_NAME "i2c2"
#endif
#endif

#ifndef ENV_ALLOW_DIAGNOSTIC_FALLBACK
#define ENV_ALLOW_DIAGNOSTIC_FALLBACK 1
#endif

#define ENV_I2C_BUS_NAME_LEN 16
#define AHT20_I2C_ADDR 0x38
#define AHT20_STATUS_BUSY 0x80
#define AHT20_STATUS_CALIBRATED 0x08

static rt_thread_t s_env_tid = RT_NULL;
static volatile rt_bool_t s_env_running = RT_FALSE;
static rt_uint32_t s_env_period_ms = ENV_WS_PERIOD_MS;
static char s_env_i2c_bus_name[ENV_I2C_BUS_NAME_LEN] = ENV_AHT20_I2C_BUS_NAME;
static rt_uint32_t s_env_fallback_seq = 0;

#ifdef PKG_USING_AHT10
static aht10_device_t s_aht_dev = RT_NULL;
#endif

#ifdef RT_USING_I2C
static struct rt_i2c_bus_device *s_i2c_bus = RT_NULL;
static char s_bound_i2c_bus_name[ENV_I2C_BUS_NAME_LEN] = {0};
static rt_bool_t s_aht20_initialized = RT_FALSE;
static rt_bool_t s_env_diag_printed = RT_FALSE;

static rt_err_t aht20_write(const rt_uint8_t *buf, rt_uint16_t len)
{
    struct rt_i2c_msg msg;

    msg.addr = AHT20_I2C_ADDR;
    msg.flags = RT_I2C_WR;
    msg.len = len;
    msg.buf = (rt_uint8_t *)buf;

    return (rt_i2c_transfer(s_i2c_bus, &msg, 1) == 1) ? RT_EOK : -RT_ERROR;
}

static rt_err_t aht20_read(rt_uint8_t *buf, rt_uint16_t len)
{
    struct rt_i2c_msg msg;

    msg.addr = AHT20_I2C_ADDR;
    msg.flags = RT_I2C_RD;
    msg.len = len;
    msg.buf = buf;

    return (rt_i2c_transfer(s_i2c_bus, &msg, 1) == 1) ? RT_EOK : -RT_ERROR;
}

static rt_err_t aht20_read_status(rt_uint8_t *status)
{
    rt_uint8_t cmd = 0x71;
    struct rt_i2c_msg msgs[2];

    if (!status)
    {
        return -RT_EINVAL;
    }

    msgs[0].addr = AHT20_I2C_ADDR;
    msgs[0].flags = RT_I2C_WR;
    msgs[0].len = 1;
    msgs[0].buf = &cmd;

    msgs[1].addr = AHT20_I2C_ADDR;
    msgs[1].flags = RT_I2C_RD;
    msgs[1].len = 1;
    msgs[1].buf = status;

    return (rt_i2c_transfer(s_i2c_bus, msgs, 2) == 2) ? RT_EOK : -RT_ERROR;
}

static rt_err_t aht20_read_status_direct(rt_uint8_t *status)
{
    if (!status)
    {
        return -RT_EINVAL;
    }

    return aht20_read(status, 1);
}

static rt_err_t aht20_soft_reset(void)
{
    rt_uint8_t cmd = 0xBA;

    if (aht20_write(&cmd, 1) != RT_EOK)
    {
        return -RT_ERROR;
    }

    rt_thread_mdelay(25);
    return RT_EOK;
}

static rt_err_t aht20_init_once(void)
{
    rt_uint8_t status = 0;
    rt_bool_t status_valid = RT_FALSE;

    if (s_aht20_initialized)
    {
        return RT_EOK;
    }

    if (!s_i2c_bus || rt_strcmp(s_bound_i2c_bus_name, s_env_i2c_bus_name) != 0)
    {
        s_i2c_bus = rt_i2c_bus_device_find(s_env_i2c_bus_name);
        if (!s_i2c_bus)
        {
            LOG_E("AHT20 I2C bus '%s' not found", s_env_i2c_bus_name);
            return -RT_ERROR;
        }
        rt_strncpy(s_bound_i2c_bus_name, s_env_i2c_bus_name, sizeof(s_bound_i2c_bus_name) - 1);
        s_bound_i2c_bus_name[sizeof(s_bound_i2c_bus_name) - 1] = '\0';
        s_aht20_initialized = RT_FALSE;
    }

    rt_thread_mdelay(40);
    if (aht20_read_status(&status) != RT_EOK)
    {
        if (aht20_read_status_direct(&status) == RT_EOK)
        {
            status_valid = RT_TRUE;
            LOG_W("AHT20 status 0x71 failed, direct status=0x%02x", status);
        }
        else
        {
            LOG_W("AHT20 status read failed, continuing with init/measure probe");
        }
    }
    else
    {
        status_valid = RT_TRUE;
    }

    if (!status_valid || ((status & AHT20_STATUS_CALIBRATED) == 0))
    {
        rt_uint8_t init_cmd[3] = {0xBE, 0x08, 0x00};
        (void)aht20_soft_reset();
        if (aht20_write(init_cmd, sizeof(init_cmd)) != RT_EOK)
        {
            LOG_E("AHT20 init command failed");
            return -RT_ERROR;
        }
        rt_thread_mdelay(40);
    }

    s_aht20_initialized = RT_TRUE;
    if (status_valid)
    {
        LOG_I("AHT20 ready on %s, status=0x%02x", s_env_i2c_bus_name, status);
    }
    else
    {
        LOG_I("AHT20 ready on %s (status unavailable)", s_env_i2c_bus_name);
    }
    return RT_EOK;
}

static void aht20_select_bus(const char *bus_name)
{
    if (!bus_name || bus_name[0] == '\0')
    {
        return;
    }

    rt_strncpy(s_env_i2c_bus_name, bus_name, sizeof(s_env_i2c_bus_name) - 1);
    s_env_i2c_bus_name[sizeof(s_env_i2c_bus_name) - 1] = '\0';
    s_i2c_bus = RT_NULL;
    s_bound_i2c_bus_name[0] = '\0';
    s_aht20_initialized = RT_FALSE;
}

static rt_err_t aht20_read_env(float *temp_c, float *humi_rh)
{
    rt_uint8_t cmd[3] = {0xAC, 0x33, 0x00};
    rt_uint8_t data[6] = {0};
    rt_uint32_t raw_humi;
    rt_uint32_t raw_temp;

    if (!temp_c || !humi_rh)
    {
        return -RT_EINVAL;
    }

    if (aht20_init_once() != RT_EOK)
    {
        return -RT_ERROR;
    }

    if (aht20_write(cmd, sizeof(cmd)) != RT_EOK)
    {
        LOG_W("AHT20 measure command failed");
        return -RT_ERROR;
    }

    rt_thread_mdelay(80);

    if (aht20_read(data, sizeof(data)) != RT_EOK)
    {
        LOG_W("AHT20 data read failed");
        return -RT_ERROR;
    }

    if (data[0] & AHT20_STATUS_BUSY)
    {
        LOG_W("AHT20 still busy");
        return -RT_EBUSY;
    }

    raw_humi = ((rt_uint32_t)data[1] << 12) | ((rt_uint32_t)data[2] << 4) | (data[3] >> 4);
    raw_temp = (((rt_uint32_t)data[3] & 0x0F) << 16) | ((rt_uint32_t)data[4] << 8) | data[5];

    *humi_rh = ((float)raw_humi * 100.0f) / 1048576.0f;
    *temp_c = ((float)raw_temp * 200.0f) / 1048576.0f - 50.0f;
    return RT_EOK;
}

static rt_err_t aht20_read_env_auto(float *temp_c, float *humi_rh)
{
    const char *fallback_buses[] = {"i2c2", "i2c1", "i2c0"};
    rt_err_t ret = aht20_read_env(temp_c, humi_rh);

    if (ret == RT_EOK)
    {
        return RT_EOK;
    }

    for (int i = 0; i < (int)(sizeof(fallback_buses) / sizeof(fallback_buses[0])); i++)
    {
        if (rt_strcmp(s_env_i2c_bus_name, fallback_buses[i]) == 0)
        {
            continue;
        }

        aht20_select_bus(fallback_buses[i]);
        ret = aht20_read_env(temp_c, humi_rh);
        if (ret == RT_EOK)
        {
            LOG_I("AHT20 found on %s", s_env_i2c_bus_name);
            return RT_EOK;
        }
    }

    return ret;
}

static rt_bool_t i2c_probe_addr(const char *bus_name, rt_uint8_t addr)
{
    struct rt_i2c_bus_device *bus = rt_i2c_bus_device_find(bus_name);
    rt_uint8_t dummy = 0;
    struct rt_i2c_msg msg;

    if (!bus)
    {
        return RT_FALSE;
    }

    msg.addr = addr;
    msg.flags = RT_I2C_WR;
    msg.len = 0;
    msg.buf = &dummy;

    return (rt_i2c_transfer(bus, &msg, 1) == 1) ? RT_TRUE : RT_FALSE;
}

#ifdef PKG_USING_AHT10
static rt_bool_t env_value_valid(float temp_c, float humi_rh)
{
    return (temp_c > -40.0f && temp_c < 85.0f && humi_rh >= 0.0f && humi_rh <= 100.0f) ? RT_TRUE : RT_FALSE;
}

static rt_err_t aht10_pkg_read_env(float *temp_c, float *humi_rh)
{
    const char *bus_name = PKG_AHT10_I2C_BUS_NAME;

    if (!temp_c || !humi_rh)
    {
        return -RT_EINVAL;
    }

    if (!s_aht_dev)
    {
        s_aht_dev = aht10_init(bus_name);
        if (!s_aht_dev)
        {
            LOG_E("AHT package init failed on %s", bus_name);
            return -RT_ERROR;
        }
        LOG_I("AHT package ready on %s", bus_name);
    }

    *temp_c = aht10_read_temperature(s_aht_dev);
    *humi_rh = aht10_read_humidity(s_aht_dev);

    if (!env_value_valid(*temp_c, *humi_rh))
    {
        LOG_W("AHT package invalid reading on %s: temp=%.2f humi=%.2f", bus_name, *temp_c, *humi_rh);
        return -RT_ERROR;
    }

    return RT_EOK;
}
#endif

static void env_make_diagnostic_reading(float *temp_c, float *humi_rh)
{
    rt_uint32_t seq = s_env_fallback_seq++;

    if (temp_c)
    {
        *temp_c = 26.0f + (float)(seq % 10) * 0.1f;
    }
    if (humi_rh)
    {
        *humi_rh = 58.0f + (float)((seq * 3) % 10) * 0.1f;
    }
}

static void env_i2c_diag_once(void)
{
    const char *buses[] = {"i2c0", "i2c1", "i2c2"};

    if (s_env_diag_printed)
    {
        return;
    }
    s_env_diag_printed = RT_TRUE;

    for (int b = 0; b < (int)(sizeof(buses) / sizeof(buses[0])); b++)
    {
        rt_bool_t found = RT_FALSE;

        if (!rt_i2c_bus_device_find(buses[b]))
        {
            LOG_W("I2C diag: %s not found", buses[b]);
            continue;
        }

        LOG_I("I2C diag: scanning %s", buses[b]);
        for (int addr = 0x03; addr <= 0x77; addr++)
        {
            if (i2c_probe_addr(buses[b], (rt_uint8_t)addr))
            {
                LOG_I("I2C diag: %s addr 0x%02x", buses[b], addr);
                found = RT_TRUE;
            }
        }

        if (!found)
        {
            LOG_W("I2C diag: %s no devices found", buses[b]);
        }
    }
}

static int env_scan_cmd(int argc, char **argv)
{
    const char *buses[] = {"i2c0", "i2c1", "i2c2"};

    if (argc >= 2)
    {
        buses[0] = argv[1];
        buses[1] = RT_NULL;
    }

    for (int b = 0; b < (int)(sizeof(buses) / sizeof(buses[0])); b++)
    {
        if (!buses[b])
        {
            continue;
        }

        rt_kprintf("Scanning %s:\n", buses[b]);
        if (!rt_i2c_bus_device_find(buses[b]))
        {
            rt_kprintf("  bus not found\n");
            continue;
        }

        rt_bool_t found = RT_FALSE;
        for (int addr = 0x03; addr <= 0x77; addr++)
        {
            if (i2c_probe_addr(buses[b], (rt_uint8_t)addr))
            {
                rt_kprintf("  0x%02x\n", addr);
                found = RT_TRUE;
            }
        }

        if (!found)
        {
            rt_kprintf("  no devices found\n");
        }
    }

    return RT_EOK;
}
MSH_CMD_EXPORT_ALIAS(env_scan_cmd, env_scan, Scan I2C buses for env sensor);

static int env_bus_cmd(int argc, char **argv)
{
    if (argc >= 2)
    {
        aht20_select_bus(argv[1]);
    }

    rt_kprintf("AHT bus: %s addr: 0x%02x\n", s_env_i2c_bus_name, AHT20_I2C_ADDR);
    return RT_EOK;
}
MSH_CMD_EXPORT_ALIAS(env_bus_cmd, env_bus, Show or set env sensor I2C bus);

static int env_read_cmd(int argc, char **argv)
{
    float temp_c = 0.0f;
    float humi_rh = 0.0f;

    if (argc >= 2)
    {
        aht20_select_bus(argv[1]);
    }

    if (aht20_read_env_auto(&temp_c, &humi_rh) == RT_EOK)
    {
        rt_kprintf("AHT %s: temp=%.2f humi=%.2f\n", s_env_i2c_bus_name, temp_c, humi_rh);
        return RT_EOK;
    }

    rt_kprintf("AHT read failed on %s. Run env_scan to check I2C addresses.\n", s_env_i2c_bus_name);
    return -RT_ERROR;
}
MSH_CMD_EXPORT_ALIAS(env_read_cmd, env_read, Read env sensor once);
#endif

rt_err_t env_read_once(float *temp_c, float *humi_rh)
{
#ifdef PKG_USING_AHT10
    if (aht10_pkg_read_env(temp_c, humi_rh) == RT_EOK)
    {
        return RT_EOK;
    }
#endif

#ifdef RT_USING_I2C
    env_i2c_diag_once();
    return aht20_read_env_auto(temp_c, humi_rh);
#else
    (void)temp_c;
    (void)humi_rh;
    return -RT_ENOSYS;
#endif
}

static void env_ws_thread_entry(void *parameter)
{
    (void)parameter;

    while (s_env_running)
    {
        const char *session_id = xz_ws_get_session_id();
        float temp_c = 0.0f;
        float humi_rh = 0.0f;
        rt_err_t ret;

#ifdef RT_USING_I2C
        ret = env_read_once(&temp_c, &humi_rh);
#else
        ret = -RT_ENOSYS;
#endif

        if (session_id && session_id[0] != '\0')
        {
            char msg[256];

            if (ret == RT_EOK)
            {
                xiaozhi_ui_set_env_result(temp_c, humi_rh);
                rt_snprintf(msg, sizeof(msg),
                            "{\"session_id\":\"%s\",\"type\":\"env\","
                            "\"temp_c\":%.2f,\"humi_rh\":%.2f,\"sensor_ok\":true,\"ts\":%u}",
                            session_id,
                            temp_c,
                            humi_rh,
                            (unsigned)rt_tick_get());
            }
            else
            {
#if ENV_ALLOW_DIAGNOSTIC_FALLBACK
                env_make_diagnostic_reading(&temp_c, &humi_rh);
                rt_snprintf(msg, sizeof(msg),
                            "{\"session_id\":\"%s\",\"type\":\"env\","
                            "\"temp_c\":%.2f,\"humi_rh\":%.2f,"
                            "\"sensor_ok\":false,\"sensor_error\":\"aht_sensor_not_found\","
                            "\"ts\":%u}",
                            session_id,
                            temp_c,
                            humi_rh,
                            (unsigned)rt_tick_get());
#else
                rt_thread_mdelay(s_env_period_ms);
                continue;
#endif
            }

            if (ws_send_text_locked(msg))
            {
                LOG_I("env uploaded: temp=%.2f humi=%.2f%s",
                      temp_c,
                      humi_rh,
                      ret == RT_EOK ? "" : " (diagnostic fallback)");
            }
            else
            {
                LOG_D("env upload skipped: websocket unavailable");
            }
        }

        rt_thread_mdelay(s_env_period_ms);
    }

    s_env_tid = RT_NULL;
}

rt_err_t env_ws_uploader_start(rt_uint32_t period_ms)
{
    if (s_env_tid)
    {
        return RT_EOK;
    }

    if (period_ms > 0)
    {
        s_env_period_ms = period_ms;
    }

    s_env_running = RT_TRUE;
    s_env_tid = rt_thread_create("env_ws",
                                 env_ws_thread_entry,
                                 RT_NULL,
                                 2048,
                                 22,
                                 10);
    if (!s_env_tid)
    {
        s_env_running = RT_FALSE;
        return -RT_ENOMEM;
    }

    rt_thread_startup(s_env_tid);
    return RT_EOK;
}
