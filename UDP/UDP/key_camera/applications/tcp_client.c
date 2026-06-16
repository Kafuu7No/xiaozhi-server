/*
 * Copyright (c) 2006-2021, RT-Thread Development Team
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Change Logs:
 * Date           Author       Notes
 * 2026-04-05     MICRODYSSEY       the first version
 */
#include <rtthread.h>
#include <wlan_mgnt.h>
#include "tcp_client.h"

static void reconnect(void *ctx);
int is_connected(TCP_CONN_T tcp_ctx)
{
    return rt_atomic_load(&tcp_ctx->_connected) == 1;
}
static void set_error_code(TCP_CONN_T tcp_ctx, err_t code)
{
    rt_atomic_store(&tcp_ctx->_tcp_result, code);
}
err_t error_code(TCP_CONN_T tcp_ctx)
{
    return rt_atomic_load(&tcp_ctx->_tcp_result);
}
/**
 * tcp 连接成功的回调。
 * @param arg
 * @param tpcb
 * @param err
 * @return
 */
static err_t tcp_connected(void *ctx, struct tcp_pcb *tpcb, err_t err)
{
    TCP_CONN_T tcp_ctx = ctx;
    if (err == ERR_OK)
    {
        TCP_LOG("connect created.\n");
        rt_atomic_store(&tcp_ctx->_connected, 1);
    }
    else
    {
        TCP_LOGF("connect fail.error code(%d)\n", err);
    }
    return ERR_OK;
}

/**
 * tcp 接收回调函数。
 * @param ctx TCP_CONN_T上下文
 * @param tpcb
 * @param p
 * @param err
 * @return
 */
static err_t tcp_recv_cb(void *ctx, struct tcp_pcb *tpcb, struct pbuf *p, err_t err)
{
    TCP_CONN_T tcp_ctx = (TCP_CONN_T) ctx;
    if (tcp_ctx->_tpcb != tpcb)
    {
        return err; // 不是当前连接，不管他了。
    }
    if (err == ERR_OK)
    {
        if (p != NULL)
        {
            if (rt_mq_send(tcp_ctx->_tcp_rx_mq, &p, sizeof(struct pbuf *)) != RT_EOK)
            {
                TCP_LOG("queue error, dropping packet");
                tcp_recved(tpcb, p->tot_len);
                pbuf_free(p);
            }
        }
        else
        {
            TCP_LOG("remote closed connection");
            reconnect(ctx);
        }
    }
    return err;
}
/**
 * tcp 发送成功回调。
 * @param ctx
 * @param tpcb
 * @param len
 * @return
 */
static err_t tcp_sent_cb(void *ctx, struct tcp_pcb *tpcb, u16_t len)
{
    TCP_CONN_T tcp_ctx = ctx;
    if (tcp_ctx->_tpcb == tpcb)
    {
        // 数据真正被 ACK 后才会调用
        tcp_ctx->_remain_send_data_count -= len;
        if (tcp_ctx->_remain_send_data_count == 0)
        {
            rt_completion_done(&tcp_ctx->_sent_done);
        }
        else if (tcp_ctx->_remain_send_data_count < 0)
        {
            TCP_LOGF("Unexpected error, _remain_send_data_count is %d", tcp_ctx->_remain_send_data_count);
            set_error_code(tcp_ctx, ERR_IF);
            rt_completion_done(&tcp_ctx->_sent_done);
        }
    }
    return ERR_OK;
}
/**
 * tcp 发生错误时回调函数。
 * @param ctx
 * @param err
 */
static void tcp_err_cb(void *ctx, err_t err)
{
    TCP_LOGF("TCP error: %d\n", err);
    reconnect(ctx);
}

/**
 * tcp 重连操作封装。因为重连操作和初次连接操作基本一致，所以在初次连接时，也可调用此函数。
 * @return 成功返回ERR_OK,失败返回其他值。
 */
static void reconnect(void *ctx)
{

    TCP_CONN_T tcp_ctx = ctx;
    err_t res;

    // 确保只有一个reconnect被执行中
    rt_atomic_t expect = 0;
    if (!rt_atomic_compare_exchange_strong(&tcp_ctx->_reconnecting, &expect, 1))
    {
        // 有其他线程在执行 reconnect，直接返回
        TCP_LOG("reconnect() already in progress.\n");
        return;
    }
    // 记录状态是连接断开
    rt_atomic_store(&tcp_ctx->_connected, 0);

//    for (int i = 0; i < 10; i++)
//    {
    do
    {
        // 关闭之前的连接
        if (tcp_ctx->_tpcb)
        {
            if (tcp_close(tcp_ctx->_tpcb) != ERR_OK)
            {
                tcp_abort(tcp_ctx->_tpcb);
            }
            tcp_ctx->_tpcb = NULL;
            // 确定释放所有的_sent_done，避免 err_cb中调用reconnect，导致外部的调用的死锁
            if (!rt_list_isempty(&(tcp_ctx->_sent_done.suspended_list)))
            {
                set_error_code(tcp_ctx, ERR_CLSD);
                rt_completion_done(&tcp_ctx->_sent_done);
            }
        }

        // 初始化 TCP 控制块
        tcp_ctx->_tpcb = tcp_new();
        if (tcp_ctx->_tpcb == NULL)
        {
            TCP_LOG("Failed to create TCP PCB\n");
            set_error_code(tcp_ctx, ERR_IF);
            return;
        }

        // 设置tcp连接保活
        ip_set_option(tcp_ctx->_tpcb, SOF_KEEPALIVE);

        // 设置 TCP 回调函数
        tcp_arg(tcp_ctx->_tpcb, (void*) tcp_ctx);
        tcp_sent(tcp_ctx->_tpcb, tcp_sent_cb);
        tcp_err(tcp_ctx->_tpcb, tcp_err_cb);
        tcp_recv(tcp_ctx->_tpcb, tcp_recv_cb);

        res = tcp_connect(tcp_ctx->_tpcb, &tcp_ctx->_server_ip, tcp_ctx->_server_port, tcp_connected);
        if (res == ERR_OK)
        {
            break;
        }

        TCP_LOGF("tcp connect fail.(err:%d)\n", res);
        rt_thread_mdelay(2000);
    } while (0);
    set_error_code(tcp_ctx, res);
    rt_atomic_store(&tcp_ctx->_reconnecting, 0);
}

static void do_reconnect(void *ctx)
{
    reconnect(ctx);
    TCP_CONN_T tcp_ctx = ctx;
    rt_completion_done(&tcp_ctx->_reconnect_done);
}

void tcp_conn_init(TCP_CONN_T tcp_ctx, ip_addr_t server_ip, u16_t server_port)
{
    memset(tcp_ctx, 0, sizeof(TCP_CONN));
    tcp_ctx->_server_ip = server_ip;
    tcp_ctx->_server_port = server_port;
    // 创建内部异步接收转同步的队列
    tcp_ctx->_tcp_rx_mq = rt_mq_create("_tcp_rx_mq", sizeof(struct pbuf *),/* 一条消息的最大长度 */
    32, /* 消息最大数量 */
    RT_IPC_FLAG_FIFO);/* 如果有多个线程等待，按照先来先得到的方法分配消息 */
    // 初始化信号量
    rt_completion_init(&tcp_ctx->_reconnect_done);
    rt_completion_init(&tcp_ctx->_sent_done);
    rt_completion_init(&tcp_ctx->_free_done);

    // 创建tcp连接
    tcpip_callback(do_reconnect, tcp_ctx);

    // 等待连接建立操作
    rt_completion_wait(&tcp_ctx->_reconnect_done, RT_WAITING_FOREVER);

    // 等待tcp连接建立成功（最多等 10 秒）。
    // 注意：连不上时绝不能 RT_ASSERT 把整块板子挂死——否则云端短暂不可用就会
    // 导致 board2 卡死、连 UDP 命令(开泵/拍照)都收不到。连不上就返回，
    // UDP 命令照常工作，TCP 会在下次 tcp_send 时自动重连。
    if (error_code(tcp_ctx) == ERR_OK)
    {
        int wait = 0;
        while (!is_connected(tcp_ctx) && wait < 20)
        {
            rt_thread_mdelay(500);
            wait++;
        }
        if (!is_connected(tcp_ctx))
        {
            rt_kprintf("tcp connect timeout, will retry on demand.\n");
        }
    }
    else
    {
        rt_kprintf("tcp connect failed, will retry on demand.\n");
    }
    tcp_ctx->_tcp_rx_mq = rt_mq_create("_tcp_rx_mq", sizeof(struct pbuf *), 32, RT_IPC_FLAG_FIFO);
    if (tcp_ctx->_tcp_rx_mq == RT_NULL)
    {
        TCP_LOG("Failed to create mq");
        RT_ASSERT(0);
    }
}
struct SendData
{
    uint8_t* data;
    uint16_t len;
};
static void do_tcp_send(void *ctx)
{
    err_t res;
    TCP_CONN_T tcp_ctx = ctx;
    const struct SendData* data_args = tcp_ctx->_other_args;
    tcp_ctx->_other_args = NULL;    // 参数取完就删除指针，避免悬空指针

    if (tcp_sndbuf(tcp_ctx->_tpcb) < data_args->len)
    {
        TCP_LOG("not enough send buffer.");
        set_error_code(tcp_ctx, ERR_MEM);
        return;
    }
    // 记录要发送的数据量，确保数据完全发送后，才会发出_sent_data信号
    tcp_ctx->_remain_send_data_count = data_args->len;

    res = tcp_write(tcp_ctx->_tpcb, data_args->data, data_args->len, TCP_WRITE_FLAG_COPY);
    if (res != ERR_OK)
    {
        set_error_code(tcp_ctx, res);
        return;
    }

    res = tcp_output(tcp_ctx->_tpcb);
    if (res != ERR_OK)
    {
        set_error_code(tcp_ctx, res);
        return;
    }

    // 等待 tcp_sent() 回调完成
    set_error_code(tcp_ctx, ERR_OK);
}

err_t tcp_send(TCP_CONN_T tcp_ctx, uint8_t*buf, uint16_t buf_size)
{
    static int err_count = 0;

    if (!is_connected(tcp_ctx))
    {
        err_count++;
        if (err_count < 10)
        {
            return ERR_CLSD;
        }
        else
        {
            tcpip_callback(do_reconnect, tcp_ctx);
            // 等待连接建立操作
            rt_completion_wait(&tcp_ctx->_reconnect_done, RT_WAITING_FOREVER);
            // 等待tcp连接建立成功（最多等 10 秒）
            if (error_code(tcp_ctx) == ERR_OK)
            {
                int wait = 0;
                while (!is_connected(tcp_ctx) && wait < 20)
                {
                    rt_thread_mdelay(500);
                    wait++;
                }
            }
            // 重连失败也绝不 RT_ASSERT 把整块板子挂死（否则云端短暂不可用/重启时，
            // board2 一旦要发照片就会卡死，连开泵等 UDP 命令都收不到）。
            // 丢弃这次发送、返回错误，下次再试；UDP 命令链路不受影响。
            if (!is_connected(tcp_ctx))
            {
                rt_kprintf("tcp reconnect failed, drop this send.\n");
                err_count = 0;
                return ERR_CLSD;
            }
        }
    }
    err_count = 0;

    // 携带上数据参数
    struct SendData data = { .data = buf, .len = buf_size };
    tcp_ctx->_other_args = &data;

    if (tcpip_callback(do_tcp_send, tcp_ctx) != ERR_OK)
    {
        return ERR_VAL;
    }
    rt_completion_wait(&tcp_ctx->_sent_done, RT_WAITING_FOREVER);
    return error_code(tcp_ctx);
}

static void do_free_pbuf(void* ctx)
{
    TCP_CONN_T tcp_ctx = ctx;
    struct pbuf * pp = tcp_ctx->_other_args;
    tcp_ctx->_other_args = NULL;    // 参数取完就删除指针，避免悬空指针

    if (tcp_ctx->_tpcb && pp->tot_len > 0)
    {
        tcp_recved(tcp_ctx->_tpcb, pp->tot_len);  //  通知 lwIP 已处理数据
    }
    pbuf_free(pp);                  //  释放 pbuf
    set_error_code(tcp_ctx, ERR_OK);
    rt_completion_done(&tcp_ctx->_free_done);
}

err_t tcp_wait_recv(TCP_CONN_T tcp_ctx, void (*handle)(void* args, struct pbuf * ptr), void* args)
{
    RT_ASSERT(handle != NULL);
    struct pbuf * ptr = NULL;
    rt_ssize_t result = rt_mq_recv(tcp_ctx->_tcp_rx_mq, &ptr, sizeof(struct pbuf *), RT_TICK_PER_SECOND * 60 * 10);
    if (result <= 0)
    {
        TCP_LOGF("rt_mq_recv failed, return value is %d", result);
        if (result == -RT_ETIMEOUT)
        {
            return ERR_TIMEOUT;
        }
        else
        {
            // 不清楚什么错，就这样返回ERR_IF吧。
            return ERR_IF;
        }
    }
    handle(args, ptr);
    // 释放pbuf
    tcp_ctx->_other_args = ptr;

    tcpip_callback(do_free_pbuf, tcp_ctx);
    rt_completion_wait(&tcp_ctx->_free_done, RT_WAITING_FOREVER);

    return error_code(tcp_ctx);
}
