/*
 * Copyright (c) 2006-2021, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-04-05     MICRODYSSEY       the first version
 */
#ifndef APPLICATIONS_TCP_CLIENT_H_
#define APPLICATIONS_TCP_CLIENT_H_

#include <rtthread.h>
#include <rtdevice.h>

#include <lwip/udp.h>
#include <lwip/tcp.h>
#include <lwip/ip.h>
#include <lwip/err.h>
#include <lwip/pbuf.h>
#include <lwip/inet_chksum.h>
#include <netif/ethernetif.h>
#include "lwip/tcpip.h"

#define MY_TCP_DEBUG

#ifdef MY_TCP_DEBUG
#define TCP_LOG(msg) rt_kprintf(msg)
#define TCP_LOGF(fmt, ...)   rt_kprintf(fmt, __VA_ARGS__)
#else
#define TCP_LOG(msg)
#define TCP_LOGF(fmt, ...)
#endif

/**
 * 该封装对象是非线程安全的，不可多线程使用。
 */
typedef struct TCP_CONN
{
    // 需要外部提供初始的部分
    ip_addr_t _server_ip;
    u16_t _server_port;

    //内部的一些状态
    rt_mq_t _tcp_rx_mq;
    struct tcp_pcb* _tpcb;
    rt_atomic_t _connected;
    rt_atomic_t _reconnecting;
    int _remain_send_data_count;

    rt_atomic_t _tcp_result;
    struct rt_completion _sent_done; // 发送同步
    struct rt_completion _reconnect_done; // 操作同步对象
    struct rt_completion _free_done;

    void* _other_args;
} TCP_CONN;
typedef struct TCP_CONN* TCP_CONN_T;

void tcp_conn_init(TCP_CONN_T tcp_ctx, ip_addr_t server_ip, u16_t server_port);
err_t tcp_send(TCP_CONN_T tcp_ctx, uint8_t*buf, uint16_t buf_size);
err_t tcp_wait_recv(TCP_CONN_T tcp_ctx, void (*handle)(void* args, struct pbuf * ptr), void* args);

#endif /* APPLICATIONS_TCP_CLIENT_H_ */
