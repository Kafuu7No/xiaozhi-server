/*
 * Copyright (c) 2006-2024, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2024-01-01     RT-Thread    First version
 */

#include <rtthread.h>
#include <webnet.h>
#include <wn_module.h>
#include <wlan_mgnt.h>
#include <dfs_file.h>
#include <dfs_fs.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <cJSON.h>
#include "wifi_manager.h"
#include "wifi_provision_config.h"
#include "xiaozhi_ui.h"

/* Declare xiaozhi init function to avoid including xiaozhi.h which has lwIP conflicts */
extern int ws_xiaozhi_init(void);

/*****************************************************************************
 * Macro Definitions
 *****************************************************************************/
#define DBG_TAG    "wifi.mgr"
#define DBG_LVL    DBG_INFO
#include <rtdbg.h>

#define RESULT_BUF_SIZE         4096
#define MAX_SCAN_RESULTS        32
#define WIFI_CONNECT_MAX_RETRY  3
#define WIFI_CONNECT_TIMEOUT_S  15
#define SD_MOUNT_TIMEOUT_S      10

#ifndef XZ_WIFI_PROVISION_SSID
#define XZ_WIFI_PROVISION_SSID  ""
#endif

#ifndef XZ_WIFI_PROVISION_PASSWORD
#define XZ_WIFI_PROVISION_PASSWORD  ""
#endif

#ifndef XZ_WIFI_PROVISION_SSID_HEX
#define XZ_WIFI_PROVISION_SSID_HEX  ""
#endif

#ifndef XZ_WIFI_PROVISION_PASSWORD_HEX
#define XZ_WIFI_PROVISION_PASSWORD_HEX  ""
#endif

/*****************************************************************************
 * Static Variables
 *****************************************************************************/
static char s_result_buffer[RESULT_BUF_SIZE];
static rt_bool_t s_sta_connected = RT_FALSE;

/* Temporary storage for current WiFi credentials */
static char s_saved_ssid[64] = {0};
static char s_saved_password[64] = {0};

/* WiFi scan results */
static struct rt_wlan_info s_scan_result[MAX_SCAN_RESULTS];
static int s_scan_cnt = 0;
static struct rt_wlan_info *s_scan_filter = RT_NULL;

static rt_err_t hex_decode_arg(const char *hex, char *out, rt_size_t out_size);

static rt_bool_t wifi_flash_fs_ready(void)
{
#ifdef BSP_USING_FLASH
    struct dfs_filesystem *fs = dfs_filesystem_lookup(WIFI_CONFIG_FILE);

    if (!fs || !fs->ops || !fs->ops->name)
    {
        return RT_FALSE;
    }

    return (rt_strcmp(fs->ops->name, "lfs") == 0) ? RT_TRUE : RT_FALSE;
#else
    return RT_FALSE;
#endif
}

/*****************************************************************************
 * Private Functions - Configuration
 *****************************************************************************/

/**
 * @brief Save WiFi configuration to SD card
 * @param ssid WiFi SSID
 * @param password WiFi password
 * @return RT_EOK on success, other values on failure
 */
static rt_err_t wifi_config_save(const char *ssid, const char *password)
{
    int fd;
    cJSON *root = RT_NULL;
    char *json_str = RT_NULL;
    rt_err_t ret;

    if (!ssid || rt_strlen(ssid) == 0)
    {
        LOG_E("Save config failed: SSID is empty");
        return -RT_EINVAL;
    }

    /* Create JSON object */
    root = cJSON_CreateObject();
    if (!root)
    {
        LOG_E("Create JSON object failed");
        return -RT_ENOMEM;
    }

    cJSON_AddStringToObject(root, "ssid", ssid);
    cJSON_AddStringToObject(root, "password", password ? password : "");

    /* Convert to JSON string */
    json_str = cJSON_Print(root);
    if (!json_str)
    {
        LOG_E("JSON print failed");
        cJSON_Delete(root);
        return -RT_ENOMEM;
    }

    /* Write to file */
    if (!wifi_flash_fs_ready())
    {
        LOG_W("Flash filesystem is not ready, skip saving WiFi config");
        ret = -RT_EBUSY;
    }
    else
    {
        fd = open(WIFI_CONFIG_FILE, O_WRONLY | O_CREAT | O_TRUNC, 0);
        if (fd >= 0)
        {
            int len = rt_strlen(json_str);
            if (write(fd, json_str, len) == len)
            {
                LOG_I("Config saved to %s", WIFI_CONFIG_FILE);
                ret = RT_EOK;
            }
            else
            {
                LOG_E("Write config file failed");
                ret = -RT_ERROR;
            }
            close(fd);
        }
        else
        {
            LOG_E("Open config file failed: %s", WIFI_CONFIG_FILE);
            ret = -RT_ERROR;
        }
    }

    cJSON_free(json_str);
    cJSON_Delete(root);

    return ret;
}

/**
 * @brief Load WiFi configuration from SD card
 * @param ssid Output buffer for WiFi SSID
 * @param ssid_len Length of ssid buffer
 * @param password Output buffer for WiFi password
 * @param password_len Length of password buffer
 * @return RT_EOK on success, other values on failure
 */
static rt_err_t wifi_config_load(char *ssid, int ssid_len, char *password, int password_len)
{
    int fd;
    char buf[256] = {0};
    cJSON *root = RT_NULL;
    cJSON *item = RT_NULL;

    if (!ssid || !password)
    {
        return -RT_EINVAL;
    }

    /* Read file */
    fd = open(WIFI_CONFIG_FILE, O_RDONLY);
    if (fd < 0)
    {
        LOG_D("Config file not found: %s", WIFI_CONFIG_FILE);
        return -RT_ENOSYS;
    }

    int len = read(fd, buf, sizeof(buf) - 1);
    close(fd);

    if (len <= 0)
    {
        LOG_E("Read config file failed");
        return -RT_ERROR;
    }

    buf[len] = '\0';

    /* Parse JSON */
    root = cJSON_Parse(buf);
    if (!root)
    {
        LOG_E("Parse config JSON failed");
        return -RT_ERROR;
    }

    /* Get SSID */
    item = cJSON_GetObjectItem(root, "ssid");
    if (item && cJSON_IsString(item) && item->valuestring)
    {
        rt_strncpy(ssid, item->valuestring, ssid_len - 1);
        ssid[ssid_len - 1] = '\0';
    }
    else
    {
        LOG_E("Config missing SSID");
        cJSON_Delete(root);
        return -RT_ERROR;
    }

    /* Get password */
    item = cJSON_GetObjectItem(root, "password");
    if (item && cJSON_IsString(item) && item->valuestring)
    {
        rt_strncpy(password, item->valuestring, password_len - 1);
        password[password_len - 1] = '\0';
    }
    else
    {
        password[0] = '\0';
    }

    LOG_I("Config loaded: SSID=%s", ssid);
    cJSON_Delete(root);

    return RT_EOK;
}

/*****************************************************************************
 * Private Functions - WiFi Scan
 *****************************************************************************/

static void wifi_scan_result_clean(void)
{
    s_scan_cnt = 0;
    rt_memset(s_scan_result, 0, sizeof(s_scan_result));
}

static int wifi_scan_result_cache(struct rt_wlan_info *info)
{
    if (s_scan_cnt >= MAX_SCAN_RESULTS)
        return -RT_EFULL;

    rt_memcpy(&s_scan_result[s_scan_cnt], info, sizeof(struct rt_wlan_info));
    s_scan_cnt++;
    return RT_EOK;
}

static void user_ap_info_callback(int event, struct rt_wlan_buff *buff, void *parameter)
{
    struct rt_wlan_info *info = (struct rt_wlan_info *)buff->data;
    int index = *((int *)parameter);

    if (wifi_scan_result_cache(info) == RT_EOK)
    {
        if (s_scan_filter == RT_NULL ||
            (s_scan_filter->ssid.len == info->ssid.len &&
             rt_memcmp(s_scan_filter->ssid.val, info->ssid.val, s_scan_filter->ssid.len) == 0))
        {
            index++;
            *((int *)parameter) = index;
        }
    }
}

static void cgi_wifi_scan(struct webnet_session *session)
{
    int ret;
    int index = 0;
    struct rt_wlan_info *info = RT_NULL;

    wifi_scan_result_clean();
    s_scan_filter = RT_NULL;

    rt_wlan_register_event_handler(RT_WLAN_EVT_SCAN_REPORT,
                                   user_ap_info_callback, &index);

    ret = rt_wlan_scan_with_info(info);
    if (ret != RT_EOK)
    {
        LOG_W("Scan failed: %d", ret);
    }

    int len = rt_snprintf(s_result_buffer, RESULT_BUF_SIZE, "[");

    for (int i = 0; i < s_scan_cnt; i++)
    {
        len += rt_snprintf(s_result_buffer + len,
                           RESULT_BUF_SIZE - len,
                           "{\"ssid\":\"%s\",\"rssi\":%d}%s",
                           s_scan_result[i].ssid.val,
                           s_scan_result[i].rssi,
                           (i == s_scan_cnt - 1) ? "" : ",");
    }

    len += rt_snprintf(s_result_buffer + len, RESULT_BUF_SIZE - len, "]");
    webnet_session_set_header(session, "application/json", 200, "OK", len);
    webnet_session_write(session, (rt_uint8_t *)s_result_buffer, len);
}

static void wlan_ready_handler(int event, struct rt_wlan_buff *buff, void *parameter)
{
    if (event == RT_WLAN_EVT_READY && !s_sta_connected)
    {
        s_sta_connected = RT_TRUE;
        LOG_I("STA connected to router successfully");

        /* Save WiFi config to SD card */
        if (s_saved_ssid[0] != '\0')
        {
            wifi_config_save(s_saved_ssid, s_saved_password);
        }

        rt_thread_mdelay(3000);

        rt_wlan_ap_stop();
        LOG_I("Soft-AP stopped. Configuration completed");

        xiaozhi_ui_clear_info();
        ws_xiaozhi_init();
    }
}

static void cgi_wifi_connect(struct webnet_session *session)
{
    struct webnet_request *request = session->request;
    const char *ssid     = webnet_request_get_query(request, "ssid");
    const char *password = webnet_request_get_query(request, "password");
    const char *mimetype = mime_get_type(".html");
    int len;

    if (!ssid || rt_strlen(ssid) == 0)
    {
        len = rt_snprintf(s_result_buffer, RESULT_BUF_SIZE,
            "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
            "<style>body{font-family:Arial;text-align:center;padding:100px;background:#f7f9fc}</style>"
            "</head><body>"
            "<h2 style=\"color:red\">Error: WiFi name (SSID) cannot be empty!</h2>"
            "<p><a href=\"/index.html\">Back</a></p>"
            "</body></html>");
    }
    else
    {
        /* Save SSID and password to temp cache, write to file after connection success */
        rt_strncpy(s_saved_ssid, ssid, sizeof(s_saved_ssid) - 1);
        s_saved_ssid[sizeof(s_saved_ssid) - 1] = '\0';
        if (password && rt_strlen(password) > 0)
        {
            rt_strncpy(s_saved_password, password, sizeof(s_saved_password) - 1);
            s_saved_password[sizeof(s_saved_password) - 1] = '\0';
        }
        else
        {
            s_saved_password[0] = '\0';
        }

        LOG_I("Connecting to SSID: %s", ssid);
        rt_err_t ret = rt_wlan_connect(ssid,
                     (password && rt_strlen(password) > 0) ? password : RT_NULL);

        if (ret == RT_EOK)
        {
            len = rt_snprintf(s_result_buffer, RESULT_BUF_SIZE,
                "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                "<style>body{font-family:Arial;text-align:center;padding:80px;background:#f7f9fc}</style>"
                "</head><body>"
                "<h2>Connecting to WiFi...</h2>"
                "<h3><strong>%s</strong></h3>"
                "<p style=\"color:green;font-size:20px\">Connected successfully!</p>"
                "Your Board will switch to the WiFi automatically.</p>"
                "</body></html>", ssid);
        }
        else
        {
            /* Connection failed, clear temp saved config */
            s_saved_ssid[0] = '\0';
            s_saved_password[0] = '\0';

            len = rt_snprintf(s_result_buffer, RESULT_BUF_SIZE,
                "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
                "<style>body{font-family:Arial;text-align:center;padding:80px;background:#f7f9fc}</style>"
                "</head><body>"
                "<h2 style=\"color:red\">Connection failed!</h2>"
                "<p>Error code: %d<br>"
                "Possible reasons: wrong password, weak signal, or router rejected.</p>"
                "<br><a href=\"/index.html\">Try again</a>"
                "</body></html>", ret);
        }
    }

    session->request->result_code = 200;
    webnet_session_set_header(session, mimetype, 200, "Ok", len);
    webnet_session_write(session, (const rt_uint8_t*)s_result_buffer, len);
}

/**
 * @brief Start AP configuration mode
 */
static void start_ap_config_mode(void)
{
    rt_err_t ret;

    /* Wait for WLAN device ready */
    LOG_I("Waiting for WLAN device ready...");
    for (int i = 0; i < 20; i++)  /* Wait up to 10 seconds */
    {
        ret = rt_wlan_set_mode(RT_WLAN_DEVICE_AP_NAME, RT_WLAN_AP);
        if (ret == RT_EOK)
        {
            break;
        }
        rt_thread_mdelay(500);
    }

    if (ret != RT_EOK)
    {
        LOG_E("WLAN AP device not ready, cannot start AP mode");
        return;
    }

    /* Start AP */
    ret = rt_wlan_start_ap("RT-Thread-AP", "123456789");
    if (ret != RT_EOK)
    {
        LOG_E("Start AP failed: %d", ret);
        return;
    }
    LOG_I("AP Started -> SSID: RT-Thread-AP Password: 123456789");

    /* Wait for AP network interface ready */
    rt_thread_mdelay(1000);

    /* Start HTTP server after AP is fully ready */
    webnet_init();
    LOG_I("HTTP Server started");

    webnet_cgi_register("wifi_connect", cgi_wifi_connect);
    webnet_cgi_register("wifi_scan", cgi_wifi_scan);

    LOG_I("=== WiFi Config Portal Ready ===");
    LOG_I("Open browser -> http://192.168.169.1");
}

/**
 * @brief Disconnect event handler
 */
static void wlan_disconnect_handler(int event, struct rt_wlan_buff *buff, void *parameter)
{
    if (event == RT_WLAN_EVT_STA_DISCONNECTED)
    {
        LOG_W("STA disconnected from router");
        s_sta_connected = RT_FALSE;
    }
}

/**
 * @brief Try to connect WiFi with saved configuration
 * @return RT_EOK on success, other values on failure
 */
static rt_err_t try_connect_with_saved_config(void)
{
    char ssid[64] = {0};
    char password[64] = {0};
    rt_err_t ret;
    int retry_cnt = 0;
    const int max_retry = 3;

    /* Load WiFi config from SD card */
    if (wifi_config_load(ssid, sizeof(ssid), password, sizeof(password)) != RT_EOK)
    {
        LOG_I("No saved config found");
        return -RT_ENOSYS;
    }

    LOG_I("Trying to connect with saved config: %s", ssid);

    /* Show connecting status on UI */
    xiaozhi_ui_show_connecting();

    /* Save to temp cache for re-saving */
    rt_strncpy(s_saved_ssid, ssid, sizeof(s_saved_ssid) - 1);
    s_saved_ssid[sizeof(s_saved_ssid) - 1] = '\0';
    rt_strncpy(s_saved_password, password, sizeof(s_saved_password) - 1);
    s_saved_password[sizeof(s_saved_password) - 1] = '\0';

    /* Ensure WLAN STA mode is set */
    rt_wlan_set_mode(RT_WLAN_DEVICE_STA_NAME, RT_WLAN_STATION);
    rt_thread_mdelay(100);

    /* Try to connect WiFi with retry mechanism */
    while (retry_cnt < max_retry)
    {
        ret = rt_wlan_connect(ssid, (password[0] != '\0') ? password : RT_NULL);
        if (ret == RT_EOK)
        {
            break;
        }

        retry_cnt++;
        LOG_W("Connect attempt %d failed: %d, retrying...", retry_cnt, ret);
        rt_thread_mdelay(1000);
    }

    if (ret != RT_EOK)
    {
        LOG_E("Connect with saved config failed after %d retries: %d", max_retry, ret);
        /* Clear temp cache */
        s_saved_ssid[0] = '\0';
        s_saved_password[0] = '\0';
        return ret;
    }

    /* Wait for connection result */
    LOG_I("Waiting for connection...");
    for (int i = 0; i < (WIFI_CONNECT_TIMEOUT_S * 2); i++)
    {
        rt_thread_mdelay(500);
        if (rt_wlan_is_connected())
        {
            LOG_I("Connected to %s successfully", ssid);
            s_sta_connected = RT_TRUE;

            xiaozhi_ui_clear_info();
            ws_xiaozhi_init();
            return RT_EOK;
        }
    }

    LOG_W("Connection timeout");
    rt_wlan_disconnect();
    s_saved_ssid[0] = '\0';
    s_saved_password[0] = '\0';
    return -RT_ETIMEOUT;
}

static rt_err_t try_connect_with_provision_config(void)
{
    char ssid[64] = {0};
    char password[64] = {0};
    rt_err_t ret;

    if (XZ_WIFI_PROVISION_SSID_HEX[0] != '\0')
    {
        ret = hex_decode_arg(XZ_WIFI_PROVISION_SSID_HEX, ssid, sizeof(ssid));
        if (ret != RT_EOK || ssid[0] == '\0')
        {
            LOG_E("Invalid provision SSID hex");
            return ret == RT_EOK ? -RT_EINVAL : ret;
        }

        if (XZ_WIFI_PROVISION_PASSWORD_HEX[0] != '\0')
        {
            ret = hex_decode_arg(XZ_WIFI_PROVISION_PASSWORD_HEX, password, sizeof(password));
            if (ret != RT_EOK)
            {
                LOG_E("Invalid provision password hex");
                return ret;
            }
        }
    }
    else if (XZ_WIFI_PROVISION_SSID[0] != '\0')
    {
        rt_strncpy(ssid, XZ_WIFI_PROVISION_SSID, sizeof(ssid) - 1);
        ssid[sizeof(ssid) - 1] = '\0';
        rt_strncpy(password, XZ_WIFI_PROVISION_PASSWORD, sizeof(password) - 1);
        password[sizeof(password) - 1] = '\0';
    }
    else
    {
        return -RT_ENOSYS;
    }

    LOG_I("Trying to connect with provision config: %s", ssid);
    return wifi_manager_connect(ssid, password[0] != '\0' ? password : RT_NULL);
}

/*****************************************************************************
 * Public Functions
 *****************************************************************************/

rt_err_t wifi_manager_connect(const char *ssid, const char *password)
{
    rt_err_t ret;

    if (!ssid || rt_strlen(ssid) == 0)
    {
        LOG_E("SSID is empty");
        return -RT_EINVAL;
    }

    rt_strncpy(s_saved_ssid, ssid, sizeof(s_saved_ssid) - 1);
    s_saved_ssid[sizeof(s_saved_ssid) - 1] = '\0';

    if (password)
    {
        rt_strncpy(s_saved_password, password, sizeof(s_saved_password) - 1);
        s_saved_password[sizeof(s_saved_password) - 1] = '\0';
    }
    else
    {
        s_saved_password[0] = '\0';
    }

    LOG_I("Serial WiFi connect: SSID=%s", s_saved_ssid);
    rt_wlan_ap_stop();
    rt_wlan_disconnect();
    rt_wlan_set_mode(RT_WLAN_DEVICE_STA_NAME, RT_WLAN_STATION);
    rt_thread_mdelay(200);

    ret = rt_wlan_connect(s_saved_ssid,
                          (s_saved_password[0] != '\0') ? s_saved_password : RT_NULL);
    if (ret != RT_EOK)
    {
        LOG_E("rt_wlan_connect failed: %d", ret);
        return ret;
    }

    LOG_I("Waiting for WiFi connection...");
    for (int i = 0; i < (WIFI_CONNECT_TIMEOUT_S * 2); i++)
    {
        rt_thread_mdelay(500);
        if (rt_wlan_is_connected())
        {
            s_sta_connected = RT_TRUE;
            wifi_config_save(s_saved_ssid, s_saved_password);
            LOG_I("Connected to %s successfully", s_saved_ssid);
            xiaozhi_ui_clear_info();
            ws_xiaozhi_init();
            return RT_EOK;
        }
    }

    LOG_E("WiFi connection timeout");
    return -RT_ETIMEOUT;
}

void wifi_manager_init(void)
{
    static rt_bool_t s_inited = RT_FALSE;

    if (s_inited)
    {
        return;
    }
    s_inited = RT_TRUE;

    /* Register event handlers */
    rt_wlan_register_event_handler(RT_WLAN_EVT_READY, wlan_ready_handler, RT_NULL);
    rt_wlan_register_event_handler(RT_WLAN_EVT_STA_DISCONNECTED, wlan_disconnect_handler, RT_NULL);

    rt_wlan_config_autoreconnect(RT_TRUE);
    LOG_I("RT-Thread WiFi auto reconnect enabled");

    /* Wait for filesystem mount */
    LOG_I("Waiting for filesystem mount...");
    for (int i = 0; i < (SD_MOUNT_TIMEOUT_S * 2); i++)
    {
        rt_thread_mdelay(500);
        if (wifi_flash_fs_ready())
        {
            LOG_I("Flash filesystem ready");
            break;
        }
    }

    /* Try to connect with saved config */
    if (try_connect_with_saved_config() == RT_EOK)
    {
        LOG_I("Auto connect succeeded, skip AP config mode");
        return;
    }

    if (try_connect_with_provision_config() == RT_EOK)
    {
        LOG_I("Provision connect succeeded, skip AP config mode");
        return;
    }

    /* Connection failed or no config, start AP config mode */
    LOG_I("Starting AP config mode...");

    /* Show AP config info on UI */
    xiaozhi_ui_show_ap_config();

    start_ap_config_mode();
}

rt_bool_t wifi_manager_is_connected(void)
{
    return s_sta_connected;
}

/* Legacy API for backward compatibility */
void wifi_init(void)
{
    wifi_manager_init();
}

static int wifi_join_cmd(int argc, char **argv)
{
    if (argc < 2)
    {
        rt_kprintf("Usage: wifi_join <ssid> [password]\n");
        return -RT_EINVAL;
    }

    return wifi_manager_connect(argv[1], argc >= 3 ? argv[2] : RT_NULL);
}
MSH_CMD_EXPORT_ALIAS(wifi_join_cmd, wifi_join, Connect WiFi and start cloud websocket);

static int hex_value(char c)
{
    if (c >= '0' && c <= '9')
    {
        return c - '0';
    }
    if (c >= 'a' && c <= 'f')
    {
        return c - 'a' + 10;
    }
    if (c >= 'A' && c <= 'F')
    {
        return c - 'A' + 10;
    }
    return -1;
}

static rt_err_t hex_decode_arg(const char *hex, char *out, rt_size_t out_size)
{
    rt_size_t hex_len;
    rt_size_t out_len;

    if (!hex || !out || out_size == 0)
    {
        return -RT_EINVAL;
    }

    hex_len = rt_strlen(hex);
    if ((hex_len % 2) != 0)
    {
        return -RT_EINVAL;
    }

    out_len = hex_len / 2;
    if (out_len >= out_size)
    {
        return -RT_EFULL;
    }

    for (rt_size_t i = 0; i < out_len; i++)
    {
        int hi = hex_value(hex[i * 2]);
        int lo = hex_value(hex[i * 2 + 1]);

        if (hi < 0 || lo < 0)
        {
            return -RT_EINVAL;
        }

        out[i] = (char)((hi << 4) | lo);
    }

    out[out_len] = '\0';
    return RT_EOK;
}

static int wifi_join_hex_cmd(int argc, char **argv)
{
    char ssid[64];
    char password[64];
    rt_err_t ret;

    if (argc < 2)
    {
        rt_kprintf("Usage: wifi_join_hex <ssid_utf8_hex> [password_utf8_hex]\n");
        return -RT_EINVAL;
    }

    ret = hex_decode_arg(argv[1], ssid, sizeof(ssid));
    if (ret != RT_EOK || ssid[0] == '\0')
    {
        rt_kprintf("Invalid SSID hex\n");
        return ret == RT_EOK ? -RT_EINVAL : ret;
    }

    password[0] = '\0';
    if (argc >= 3)
    {
        ret = hex_decode_arg(argv[2], password, sizeof(password));
        if (ret != RT_EOK)
        {
            rt_kprintf("Invalid password hex\n");
            return ret;
        }
    }

    return wifi_manager_connect(ssid, password[0] != '\0' ? password : RT_NULL);
}
MSH_CMD_EXPORT_ALIAS(wifi_join_hex_cmd, wifi_join_hex, Connect WiFi using UTF-8 hex strings);
