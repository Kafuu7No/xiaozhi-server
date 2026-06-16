 /* Copyright (c) 2006-2024, RT-Thread Development Team
 * SPDX-License-Identifier: Apache-2.0
 *
 * 功能： UDP 控制PTC06 摄像头拍照 + 继电
 * 硬件：PSOC62-IFX-EVAL-KIT
 */
#include <rtthread.h>
#include <rtdevice.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

#include "drv_gpio.h"
#include <wlan_mgnt.h>
#include <lwip/udp.h>
#include <lwip/ip.h>
#include "ptc_06.h"
#include "tcp_client.h"

/* ==================== 硬件引脚定义 ==================== */
#define LED_PIN         GET_PIN(0, 1)
#define RELAY_PIN       GET_PIN(5, 6)      // P5.6

/* ==================== 继电器配置 ==================== */
#define RELAY_DEFAULT_MS    5000
#define COOLDOWN_MS         2000

typedef enum {
    RELAY_IDLE = 0,
    RELAY_ACTIVE,
    RELAY_COOLDOWN
} relay_state_t;

static relay_state_t relay_state = RELAY_IDLE;
static rt_timer_t relay_timer = NULL;
static rt_timer_t cooldown_timer = NULL;

/* ==================== UDP 配置 ==================== */
#define UDP_TARGET_IP    "192.168.137.1"   // 本机热点 XiaoZhiLab 的网关IP（云端所在电脑）
#define UDP_TARGET_PORT  8848
#define UDP_LOCAL_PORT   8848
#define DATA_SIZE        1500              // 每包最大字节数

static struct udp_pcb *udp_pcb = NULL;
static ip_addr_t target_addr;
static uint32_t send_packet_count = 0;     // 每次拍照清零

/* ==================== TCP 配置（照片可靠上传） ==================== */
// 照片改用 TCP 上传，避免 UDP 在拥挤的 2.4GHz 上丢包导致图片缺块/丢失。
// 命令(0x01/0x10/0x11)仍走 UDP 8848；照片走 TCP 8849。
#define TCP_SERVER_IP    "192.168.137.1"   // 云端电脑（与 UDP_TARGET_IP 相同）
#define TCP_SERVER_PORT  8849
#define TCP_CHUNK_SIZE   1460              // 每次 tcp_send 字节数（< TCP_SND_BUF）
static TCP_CONN photo_tcp;                 // 照片上传 TCP 连接
static uint8_t *g_photo_buf = NULL;        // 整张照片缓冲（收齐后再发，防半截帧）
static uint32_t g_photo_idx = 0;
static uint32_t g_photo_cap = 0;

/* ==================== 调试输出 ==================== */
#define DEBUG_ENABLE
#ifdef DEBUG_ENABLE
#define DEBUG_LOG(msg)      rt_kprintf("[DEBUG] %s\n", msg)
#define DEBUG_LOGF(fmt, ...) rt_kprintf("[DEBUG] " fmt, ##__VA_ARGS__)
#define ERROR_LOG(msg)      rt_kprintf("[ERROR] %s\n", msg)
#define ERROR_LOGF(fmt, ...) rt_kprintf("[ERROR] " fmt, ##__VA_ARGS__)
#define INFO_LOG(msg)       rt_kprintf("[INFO] %s\n", msg)
#define INFO_LOGF(fmt, ...) rt_kprintf("[INFO] " fmt, ##__VA_ARGS__)
#else
#define DEBUG_LOG(msg)
#define DEBUG_LOGF(fmt, ...)
#define ERROR_LOG(msg)
#define ERROR_LOGF(fmt, ...)
#define INFO_LOG(msg)
#define INFO_LOGF(fmt, ...)
#endif

/* ==================== 全局变量 ==================== */
static rt_device_t camera_serial = NULL;
static rt_atomic_t is_uploading = 0;
static rt_atomic_t photo_request = 0;

static struct rt_messagequeue camera_rx_mq;
static char camera_msg_pool[256];
static PTC06 camera;

#define PHOTO_FRAG_SIZE     ((RT_SERIAL_RB_BUFSZ - 10) / 8 * 8)
#define MAX_PHOTO_SIZE       (50 * 1024)

/* ==================== 函数声明 ==================== */
static void relay_on(uint32_t duration_ms);
static void relay_off(void);
static void relay_timer_cb(void *param);
static void cooldown_timer_cb(void *param);
static int take_photo_and_upload(void);
static void udp_send_data(uint8_t *data, uint16_t len);
static void udp_recv_callback(void *arg, struct udp_pcb *upcb, struct pbuf *p,
                              const ip_addr_t *addr, u16_t port);
static void udp_app_init(void);

/* ==================== UDP 通信 ==================== */
static void udp_send_data(uint8_t *data, uint16_t len)
{
    if (udp_pcb == NULL) {
        ERROR_LOG("udp_pcb is NULL");
        return;
    }
    struct pbuf *p = pbuf_alloc(PBUF_TRANSPORT, len, PBUF_RAM);
    if (p == NULL) {
        ERROR_LOG("pbuf_alloc failed");
        return;
    }
    memcpy(p->payload, data, len);
    err_t err = udp_sendto(udp_pcb, p, &target_addr, UDP_TARGET_PORT);
    pbuf_free(p);
    if (err == ERR_OK) {
        send_packet_count++;
        DEBUG_LOGF("UDP sent %d bytes to %s:%d (packet #%d)\n", len,
                   ipaddr_ntoa(&target_addr), UDP_TARGET_PORT, send_packet_count);
    } else {
        ERROR_LOGF("udp_sendto failed with err=%d\n", err);
    }
}

/* UDP 接收回调 */
static void udp_recv_callback(void *arg, struct udp_pcb *upcb, struct pbuf *p,
                              const ip_addr_t *addr, u16_t port)
{
    if (p == NULL) return;
    uint8_t *data = (uint8_t*)p->payload;
    uint16_t len = p->len;
    if (len < 1) {
        pbuf_free(p);
        return;
    }
    char from_ip[16];
    ipaddr_ntoa_r(addr, from_ip, sizeof(from_ip));
    INFO_LOGF("UDP rx %d bytes from %s:%d, cmd=0x%02X\n", len, from_ip, port, data[0]);

    switch (data[0]) {
        case 0x01:      // 拍照命令
            rt_atomic_store(&photo_request, 1);
            break;
        case 0x10:      // 仅继电器吸合 + 时长(小端4字节)，不拍照（手动/定时放水）
            if (len >= 5) {
                uint32_t dur = data[1] | (data[2]<<8) | (data[3]<<16) | (data[4]<<24);
                if (dur == 0) dur = RELAY_DEFAULT_MS;
                if (dur > 600000) dur = 600000;
                if (relay_state == RELAY_IDLE) {
                    relay_on(dur);
                } else {
                    INFO_LOG("relay busy, ignore");
                }
            }
            break;
        case 0x12:      // 继电器吸合 + 拍照 + 时长(小端4字节)，仅“3次猫叫触发”使用
            if (len >= 5) {
                uint32_t dur = data[1] | (data[2]<<8) | (data[3]<<16) | (data[4]<<24);
                if (dur == 0) dur = RELAY_DEFAULT_MS;
                if (dur > 600000) dur = 600000;
                if (relay_state == RELAY_IDLE) {
                    relay_on(dur);
                    rt_atomic_store(&photo_request, 1);
                    INFO_LOG("Photo request set from meow relay (0x12)");
                } else {
                    INFO_LOG("relay busy, ignore (0x12)");
                }
            }
            break;
        case 0x11:      // 继电器断开
            if (relay_state == RELAY_ACTIVE) {
                relay_off();
            } else {
                INFO_LOG("relay not active, ignore off");
            }
            break;
        default:
            break;
    }
    pbuf_free(p);
}

static void udp_app_init(void)
{
    ipaddr_aton(UDP_TARGET_IP, &target_addr);
    INFO_LOGF("UDP target: %s:%d\n", ipaddr_ntoa(&target_addr), UDP_TARGET_PORT);

    udp_pcb = udp_new();
    if (udp_pcb == NULL) {
        ERROR_LOG("udp_new failed");
        RT_ASSERT(0);
    }

    err_t err = udp_bind(udp_pcb, IP_ADDR_ANY, UDP_LOCAL_PORT);
    if (err != ERR_OK) {
        ERROR_LOGF("udp_bind failed, err=%d\n", err);
        RT_ASSERT(0);
    }
    INFO_LOGF("UDP bound to local port %d\n", UDP_LOCAL_PORT);

    udp_recv(udp_pcb, udp_recv_callback, NULL);
    INFO_LOG("UDP initialized");
}

/* ==================== 继电器控制 ==================== */
static void relay_on(uint32_t duration_ms)
{
    if (relay_state != RELAY_IDLE) {
        INFO_LOGF("relay_on blocked, state=%d\n", relay_state);
        return;
    }
    rt_pin_write(RELAY_PIN, PIN_HIGH);
    rt_pin_write(LED_PIN, PIN_HIGH);
    relay_state = RELAY_ACTIVE;
    INFO_LOG("RELAY ON");
    rt_timer_stop(relay_timer);
    rt_timer_control(relay_timer, RT_TIMER_CTRL_SET_TIME, &duration_ms);
    rt_timer_start(relay_timer);
    /* 注意：开泵不再自动拍照。拍照只在“猫叫触发”(0x12) 或显式拍照(0x01) 时进行，
     * 手动(0x10)/定时放水都不拍照。 */
}

static void relay_off(void)
{
    if (relay_state == RELAY_ACTIVE) {
        rt_timer_stop(relay_timer);
        rt_pin_write(RELAY_PIN, PIN_LOW);
        rt_pin_write(LED_PIN, PIN_LOW);
        relay_state = RELAY_COOLDOWN;
        uint32_t cd = COOLDOWN_MS;
        rt_timer_stop(cooldown_timer);
        rt_timer_control(cooldown_timer, RT_TIMER_CTRL_SET_TIME, &cd);
        rt_timer_start(cooldown_timer);
        INFO_LOG("RELAY OFF, cooldown start");
    } else if (relay_state == RELAY_IDLE) {
        rt_pin_write(RELAY_PIN, PIN_LOW);
        rt_pin_write(LED_PIN, PIN_LOW);
    } else {
        INFO_LOGF("relay_off invalid state %d\n", relay_state);
    }
}

static void relay_timer_cb(void *param)
{
    rt_pin_write(RELAY_PIN, PIN_LOW);
    rt_pin_write(LED_PIN, PIN_LOW);
    relay_state = RELAY_COOLDOWN;
    uint32_t cd = COOLDOWN_MS;
    rt_timer_stop(cooldown_timer);
    rt_timer_control(cooldown_timer, RT_TIMER_CTRL_SET_TIME, &cd);
    rt_timer_start(cooldown_timer);
    INFO_LOG("RELAY auto OFF");
}

static void cooldown_timer_cb(void *param)
{
    relay_state = RELAY_IDLE;
    INFO_LOG("Cooldown finished");
}

/* ==================== 摄像头驱动 ==================== */
static rt_err_t camera_rx_cb(rt_device_t dev, rt_size_t size)
{
    if (dev == camera_serial) {
        if (rt_mq_send(&camera_rx_mq, &size, sizeof(size)) != RT_EOK) {
            ERROR_LOG("camera mq full");
            return -RT_EFULL;
        }
        return RT_EOK;
    }
    return RT_EINVAL;
}

int camera_write(uint8_t *buf, uint16_t len)
{
#ifdef UART_DEBUG
    DEBUG_LOGF("camera write: ");
    for (int i = 0; i < len; i++) rt_kprintf("%02x ", buf[i]);
    rt_kprintf("\n");
#endif
    return rt_device_write(camera_serial, 0, buf, len);
}

uint32_t camera_read(uint8_t **buf_ptr, int32_t len)
{
    rt_size_t size = 0;
    uint32_t rx_len = 0;
    uint8_t *rx_buf = NULL;
    uint32_t rx_buf_size = 0;
    rt_bool_t const_buf = RT_FALSE;

    // 首字节最多等 2 秒：相机若卡住（读到一半不再回数据），超时放弃这张，
    // 而不是 RT_WAITING_FOREVER 永久阻塞整块板子（之前必须重启才能恢复）。
    rt_ssize_t res = rt_mq_recv(&camera_rx_mq, &size, sizeof(rt_size_t),
                                rt_tick_from_millisecond(2000));
    if (res < 0) {
        if (len == READ_ALLOC) {
            *buf_ptr = NULL;
        }
        ERROR_LOG("camera mq recv timeout/fail");
        return 0;
    }

    if (len == READ_ALLOC) {
        rx_buf = (uint8_t*)rt_malloc(size);
        rx_buf_size = size;
        *buf_ptr = rx_buf;
    } else if (size <= (rt_size_t)len) {
        rx_buf = *buf_ptr;
        rx_buf_size = len;
        const_buf = RT_TRUE;
    } else {
        rx_buf = (uint8_t*)rt_malloc(size);
        rx_buf_size = size;
        *buf_ptr = rx_buf;
        ERROR_LOG("alloc larger buffer");
    }

    while (res > 0) {
        if (!rx_buf) {
            ERROR_LOG("rx_buf NULL");
            return 0;
        }
        if (rx_len + size > rx_buf_size) {
            if (const_buf) {
                ERROR_LOG("buffer overflow");
                break;
            }
            uint8_t *newb = (uint8_t*)rt_realloc(rx_buf, rx_len + size);
            if (!newb) {
                ERROR_LOG("realloc fail");
                return 0;
            }
            rx_buf = newb;
            rx_buf_size = rx_len + size;
            *buf_ptr = rx_buf;
        }
        rx_len += rt_device_read(camera_serial, 0, rx_buf + rx_len, size);
        res = rt_mq_recv(&camera_rx_mq, &size, sizeof(size), 10);
    }
    *buf_ptr = rx_buf;
    return rx_len;
}

void camera_read_free(void *ptr)
{
    if (ptr) rt_free(ptr);
}

void camera_init(char *uart_name)
{
    INFO_LOGF("camera init on %s\n", uart_name);
    camera_serial = rt_device_find(uart_name);
    RT_ASSERT(camera_serial != NULL);
    rt_kprintf("%s found\n", uart_name);

    RT_ASSERT(rt_mq_init(&camera_rx_mq, "camera_mq", camera_msg_pool,
                         sizeof(rt_size_t), sizeof(camera_msg_pool),
                         RT_IPC_FLAG_FIFO) == RT_EOK);
    rt_kprintf("mq init\n");

    RT_ASSERT(rt_device_open(camera_serial, RT_DEVICE_FLAG_INT_RX) == RT_EOK);
    rt_kprintf("%s opened\n", uart_name);

    rt_device_set_rx_indicate(camera_serial, camera_rx_cb);
    init_ptc06(&camera, camera_write, camera_read, camera_read_free);

    rt_thread_mdelay(2500);
    RT_ASSERT(camera.reset(&camera) == 0);
    INFO_LOG("camera reset ok");
    camera.clear_photo_cache(&camera);
    INFO_LOG("camera ready");
}

/* ==================== UDP 发送照片数据 ==================== */
static uint8_t local_buf[DATA_SIZE];
static uint16_t local_idx = 0;

static int camera_data_send(uint8_t *buf, uint16_t len, rt_bool_t is_end)
{
    if (buf != NULL && local_idx + len < DATA_SIZE) {
        memcpy(local_buf + local_idx, buf, len);
        local_idx += len;
        return 0;
    }

    uint16_t send_len = local_idx;

    udp_send_data(local_buf, send_len);
    if (send_len > 0) {
        rt_thread_mdelay(8);   // 发包间隔，给接收端留处理时间，避免突发丢包(图片尾部灰块)
    }
    local_idx = 0;

    if (buf != NULL && local_idx + len < DATA_SIZE) {
        memcpy(local_buf + local_idx, buf, len);
        local_idx += len;
    }
    return 0;
}

// 照片分片回调：把相机读到的分片顺序拷进整张缓冲（收齐后再经 TCP 发）
int camera_frag_handle(uint8_t *buf, uint16_t len)
{
    if (g_photo_buf == NULL || g_photo_idx + len > g_photo_cap) {
        ERROR_LOG("photo buffer overflow");
        return 1;
    }
    memcpy(g_photo_buf + g_photo_idx, buf, len);
    g_photo_idx += len;
    return 0;
}

int camera_end_cb(void)
{
    return 0;
}

/* ==================== 拍照上传（TCP 可靠传输） ==================== */
int take_photo_and_upload(void)
{
    if (rt_atomic_load(&is_uploading)) {
        INFO_LOG("upload busy, skip");
        return -1;
    }
    rt_atomic_store(&is_uploading, 1);
    INFO_LOG("start photo");

    int ret = -1;
    uint8_t *photo_buf = NULL;
    do {
        if (camera.clear_photo_cache(&camera)) break;
        rt_thread_mdelay(200);
        if (camera.take_photo(&camera)) break;
        INFO_LOG("photo taken");
        rt_thread_mdelay(300);

        uint16_t size;
        if (camera.get_photo_size(&camera, &size)) break;
        INFO_LOGF("photo size=%d\n", size);
        if (size == 0 || size > MAX_PHOTO_SIZE) break;

        // 先把整张图读进 RAM
        photo_buf = (uint8_t*)rt_malloc(size);
        if (photo_buf == NULL) { ERROR_LOG("photo malloc fail"); break; }
        g_photo_buf = photo_buf; g_photo_idx = 0; g_photo_cap = size;

        if (get_photo_binary_with_cb(&camera, size, PHOTO_FRAG_SIZE,
                                      camera_frag_handle, camera_end_cb)) break;
        if (g_photo_idx != size) {
            ERROR_LOGF("incomplete photo %u/%u\n", (unsigned)g_photo_idx, (unsigned)size);
            break;
        }

        // 经 TCP 发送：[4字节小端长度][JPEG数据]，整张收齐才发，避免半截帧错位
        uint8_t hdr[4] = { (uint8_t)size, (uint8_t)(size >> 8),
                           (uint8_t)(size >> 16), (uint8_t)(size >> 24) };
        if (tcp_send(&photo_tcp, hdr, 4) != ERR_OK) { ERROR_LOG("tcp header send fail"); break; }

        uint32_t off = 0;
        int tcp_ok = 1;
        while (off < size) {
            uint16_t chunk = (size - off > TCP_CHUNK_SIZE) ? TCP_CHUNK_SIZE : (uint16_t)(size - off);
            if (tcp_send(&photo_tcp, photo_buf + off, chunk) != ERR_OK) {
                ERROR_LOG("tcp data send fail");
                tcp_ok = 0;
                break;
            }
            off += chunk;
        }
        if (!tcp_ok) break;

        INFO_LOG("upload done");
        ret = 0;
    } while(0);

    g_photo_buf = NULL; g_photo_idx = 0; g_photo_cap = 0;
    if (photo_buf) rt_free(photo_buf);
    rt_atomic_store(&is_uploading, 0);
    return ret;
}

/* ==================== WiFi 连接 ==================== */
void wlan_connect(char *ssid, char *psw)
{
    if (rt_wlan_is_connected()) return;
    while (rt_wlan_connect(ssid, psw) != RT_EOK) {
        ERROR_LOG("wifi fail, retry");
        rt_thread_mdelay(1000);
    }
    while (!rt_wlan_is_ready()) {
        INFO_LOG("wait wifi");
        rt_thread_mdelay(500);
    }
    rt_thread_mdelay(2000);
    INFO_LOG("wifi ok");
}

/* ==================== LED 指示 ==================== */
static void led_set_status(int state)
{
    switch (state) {
        case 0: rt_pin_write(LED_PIN, PIN_LOW); break;
        case 1: rt_pin_write(LED_PIN, PIN_HIGH); break;
        case 2:
            for (int i = 0; i < 3; i++) {
                rt_pin_write(LED_PIN, PIN_HIGH);
                rt_thread_mdelay(200);
                rt_pin_write(LED_PIN, PIN_LOW);
                rt_thread_mdelay(200);
            }
            break;
    }
}

/* ==================== 系统初始化 ==================== */
static void system_init(void)
{
    rt_pin_mode(LED_PIN, PIN_MODE_OUTPUT);
    rt_pin_mode(RELAY_PIN, PIN_MODE_OUTPUT);
    rt_pin_write(LED_PIN, PIN_LOW);
    rt_pin_write(RELAY_PIN, PIN_LOW);
    relay_timer = rt_timer_create("relay_tmr", relay_timer_cb,
                                  NULL, 0, RT_TIMER_FLAG_SOFT_TIMER | RT_TIMER_FLAG_ONE_SHOT);
    if (relay_timer == NULL) {
        ERROR_LOG("Failed to create relay_timer");
        RT_ASSERT(0);
    }
    cooldown_timer = rt_timer_create("cooldown_tmr", cooldown_timer_cb,
                                     NULL, 0, RT_TIMER_FLAG_SOFT_TIMER | RT_TIMER_FLAG_ONE_SHOT);
    if (cooldown_timer == NULL) {
        ERROR_LOG("Failed to create cooldown_timer");
        RT_ASSERT(0);
    }
    INFO_LOG("System init OK");
}

/* ==================== main 函数 ==================== */
int main(void)
{
    INFO_LOG("========================================");
    INFO_LOG(" PSoC62 Camera + Relay (UDP, 1400B/pkt, no trim)");
    INFO_LOG("========================================");

    system_init();
    wlan_connect("XiaoZhiLab", "xiaozhi204");//WiFi名称，WiFi密码
    udp_app_init();
    camera_init("uart0");

    // 初始化照片上传 TCP 连接（连到云端 TCP_SERVER_PORT，阻塞直到连上）
    {
        ip_addr_t tcp_ip;
        ipaddr_aton(TCP_SERVER_IP, &tcp_ip);
        tcp_conn_init(&photo_tcp, tcp_ip, TCP_SERVER_PORT);
        INFO_LOGF("TCP photo channel connected to %s:%d\n", TCP_SERVER_IP, TCP_SERVER_PORT);
    }

    INFO_LOGF("UDP packet size: %d bytes, no delay, no ACK, no trimming\n", DATA_SIZE);
    INFO_LOG("Commands (hex, UDP, no response):");
    INFO_LOG("  01         -> take photo");                          //01 拍照
    INFO_LOG("  10 + 4byte -> relay on (LE duration ms), NO photo"); //10 仅继电器闭合(手动/定时, 不拍照)
    INFO_LOG("  12 + 4byte -> relay on (LE duration ms) + photo");   //12 继电器闭合并拍照(猫叫触发)
    INFO_LOG("  11         -> relay off");                           //11 继电器断开
    INFO_LOG("========================================");

    while (1) {
        if (rt_atomic_load(&photo_request)) {
            rt_atomic_store(&photo_request, 0);
            rt_kprintf("Main loop: photo request detected, taking photo...\n");
            led_set_status(1);
            int ret = take_photo_and_upload();
            led_set_status(ret == 0 ? 0 : 2);
            rt_kprintf("Main loop: photo result %d\n", ret);
        }
        rt_thread_mdelay(10);
    }
    return 0;
}

#ifdef RT_USING_FINSH
#include <finsh.h>
static int cmd_take_photo(int argc, char **argv)
{
    rt_atomic_store(&photo_request, 1);
    return 0;
}
MSH_CMD_EXPORT(cmd_take_photo, take photo);

static int cmd_status(int argc, char **argv)
{
    const char *s = "UNKNOWN";
    switch (relay_state) {
        case RELAY_IDLE: s = "IDLE"; break;
        case RELAY_ACTIVE: s = "ACTIVE"; break;
        case RELAY_COOLDOWN: s = "COOLDOWN"; break;
    }
    rt_kprintf("WiFi: %s\n", rt_wlan_is_connected() ? "ON" : "OFF");
    rt_kprintf("Uploading: %s\n", rt_atomic_load(&is_uploading) ? "YES" : "NO");
    rt_kprintf("Relay: %s\n", s);
    rt_kprintf("UDP packets sent in last photo: %d\n", send_packet_count);
    return 0;
}
MSH_CMD_EXPORT(cmd_status, show status);
#endif
