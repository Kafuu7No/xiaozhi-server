/*
 * Capture microphone audio and run local meow detector model once.
 */

#include <rtthread.h>
#include <rtdevice.h>
#include <board.h>
#include <string.h>

#ifdef RT_USING_FINSH
#include <finsh.h>
#endif

#define DBG_TAG "meow.det"
#define DBG_LVL DBG_LOG
#include <rtdbg.h>

#include "edge-impulse-sdk/tensorflow/lite/micro/micro_interpreter.h"
#include "edge-impulse-sdk/tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "edge-impulse-sdk/tensorflow/lite/schema/schema_generated.h"

#include "tflite-model/tflite-resolver.h"

// Avoid RT-Thread legacy ALIGN macro clash
#ifdef ALIGN
#undef ALIGN
#endif
#include "tflite-model/best_model_qat_int8.h"

// UI helpers
#include "env_ws_uploader.h"
#include "xiaozhi.h"
#include "xiaozhi_ui.h"

/* Audio device name */
#ifndef BSP_XIAOZHI_MIC_DEVICE_NAME
#define BSP_XIAOZHI_MIC_DEVICE_NAME "mic0"
#endif

namespace {

// Board LEDs (from cycfg_pins.h: P16_7 red, P16_6 green, P16_5 blue)
constexpr int kLedRed = GET_PIN(16, 7);
constexpr int kLedGreen = GET_PIN(16, 6);
constexpr int kLedBlue = GET_PIN(16, 5);
// LED polarity:
// - active-high: PIN_HIGH=ON, PIN_LOW=OFF
// - active-low : PIN_LOW =ON, PIN_HIGH=OFF
// If your LEDs behave inverted, toggle this value.
constexpr int kLedActiveLow = 0;

static void led_write(int pin, rt_bool_t on)
{
    rt_pin_write(pin, (on ^ (kLedActiveLow ? 1 : 0)) ? PIN_HIGH : PIN_LOW);
}

static void leds_init_once(void)
{
    static rt_bool_t inited = RT_FALSE;
    if (inited)
        return;
    inited = RT_TRUE;

    rt_pin_mode(kLedRed, PIN_MODE_OUTPUT);
    rt_pin_mode(kLedGreen, PIN_MODE_OUTPUT);
    rt_pin_mode(kLedBlue, PIN_MODE_OUTPUT);

    // Default: detector not running -> red on, green off, blue off
    led_write(kLedRed, RT_TRUE);
    led_write(kLedGreen, RT_FALSE);
    led_write(kLedBlue, RT_FALSE);
}

constexpr int kSampleRate = 16000; // used for info only
constexpr size_t kInputSamples = 32000; // model input length

// Quant params from PC analysis
constexpr float kInScale = 0.0078431377f;
constexpr int kInZeroPoint = 0;
constexpr float kOutScale = 0.00390625f;
constexpr int kOutZeroPoint = -128;

// Detection threshold (0.0 ~ 1.0)
constexpr float kMeowThreshold = 0.6f;
// Cooldown only prevents repeated triggers; lower = more responsive.
constexpr uint32_t kDetectCooldownMs = 500;
// Sliding window hop size (in samples). 16000 @16kHz ~= 1000ms.
constexpr size_t kHopSamples = 16000;

constexpr size_t kTensorArenaSize = 256 * 1024;
__attribute__((aligned(16))) static uint8_t tensor_arena[kTensorArenaSize] rt_section(".m33_m55_shared_hyperram");

static tflite::MicroInterpreter *g_interp = RT_NULL;
static TfLiteTensor *g_in = RT_NULL;
static TfLiteTensor *g_out = RT_NULL;
static rt_tick_t g_last_detect_tick = 0;
static rt_thread_t g_meow_tid = RT_NULL;
static volatile rt_bool_t g_meow_running = RT_FALSE;
static rt_device_t g_mic_dev = RT_NULL;
static rt_tick_t g_blue_blink_until = 0;
static rt_tick_t g_blue_blink_next_toggle = 0;
static rt_bool_t g_blue_blink_on = RT_FALSE;

static void blue_blink_for_ms(uint32_t duration_ms, uint32_t period_ms)
{
    /* Non-blocking blink: handled in the detect thread loop */
    if (period_ms == 0)
        period_ms = 100;
    const rt_tick_t now = rt_tick_get();
    g_blue_blink_until = now + rt_tick_from_millisecond(duration_ms);
    g_blue_blink_next_toggle = now;
    g_blue_blink_on = RT_FALSE;
}

static int init_model()
{
    if (g_interp)
        return 0;

    const tflite::Model *model = tflite::GetModel(best_model_qat_int8);
    if (!model)
    {
        LOG_E("GetModel failed");
        return -RT_ERROR;
    }

    EI_TFLITE_RESOLVER
    static tflite::MicroInterpreter interp(model, resolver, tensor_arena, kTensorArenaSize);
    if (interp.AllocateTensors(true) != kTfLiteOk)
    {
        LOG_E("AllocateTensors failed (arena=%d)", (int)kTensorArenaSize);
        return -RT_ERROR;
    }

    g_interp = &interp;
    g_in = g_interp->input(0);
    g_out = g_interp->output(0);
    return 0;
}

#ifdef RT_USING_FINSH
static void led_probe(void)
{
    leds_init_once();
    rt_kprintf("\n[led_probe] Toggle LED pins HIGH/LOW: R=P16_7, G=P16_6, B=P16_5\n");
    rt_kprintf("[led_probe] Please observe which level turns each LED ON.\n\n");

    struct
    {
        const char *name;
        int pin;
    } leds[] = {
        {"RED  (P16_7)", kLedRed},
        {"GREEN(P16_6)", kLedGreen},
        {"BLUE (P16_5)", kLedBlue},
    };

    for (size_t i = 0; i < sizeof(leds) / sizeof(leds[0]); i++)
    {
        rt_kprintf("[led_probe] %s: write HIGH for 1000ms\n", leds[i].name);
        rt_pin_write(leds[i].pin, PIN_HIGH);
        rt_thread_mdelay(1000);

        rt_kprintf("[led_probe] %s: write LOW  for 1000ms\n", leds[i].name);
        rt_pin_write(leds[i].pin, PIN_LOW);
        rt_thread_mdelay(1000);

        rt_kprintf("[led_probe] %s: OFF via led_write(false)\n\n", leds[i].name);
        led_write(leds[i].pin, RT_FALSE);
        rt_thread_mdelay(300);
    }

    rt_kprintf("[led_probe] Done.\n");
}
MSH_CMD_EXPORT(led_probe, Toggle LED pins HIGH/LOW to determine polarity);
#endif

static inline int8_t clamp_i8(int32_t v)
{
    if (v > 127)
        return 127;
    if (v < -128)
        return -128;
    return (int8_t)v;
}

static void pcm16_to_int8(const int16_t *pcm, int8_t *dst, size_t n)
{
    for (size_t i = 0; i < n; i++)
    {
        // int16 -> float [-1, 1)
        const float x = (float)pcm[i] / 32768.0f;
        const int32_t q = (int32_t)(x / kInScale + (float)kInZeroPoint);
        dst[i] = clamp_i8(q);
    }
}

/*
 * PDM driver configuration (same as wakeword).
 */
#ifdef ENABLE_STEREO_INPUT_FEED
    #define PDM_FRAME_SAMPLES 320
    #define PDM_MONO_FRAME_SAMPLES (PDM_FRAME_SAMPLES / 2)
    #define PDM_IS_STEREO 1
#else
    #define PDM_FRAME_SAMPLES 160
    #define PDM_MONO_FRAME_SAMPLES PDM_FRAME_SAMPLES
    #define PDM_IS_STEREO 0
#endif
#define PDM_FRAME_SIZE (PDM_FRAME_SAMPLES * sizeof(int16_t))

} // namespace

static int meow_infer_from_pcm(const int16_t *pcm, float *out_score, rt_bool_t *out_detected)
{
#ifndef RT_USING_AUDIO
    LOG_E("RT_USING_AUDIO not enabled");
    return -RT_ERROR;
#else
    if (init_model() != 0)
        return -RT_ERROR;

    leds_init_once();

    // Place large buffers in HyperRAM to avoid internal RAM overflow
    static int8_t in_q[kInputSamples] rt_section(".m33_m55_shared_hyperram");

    // Quantize and run
    pcm16_to_int8(pcm, in_q, kInputSamples);

    if (!g_in || !g_out || g_in->type != kTfLiteInt8)
    {
        LOG_E("Unexpected input tensor");
        return -RT_ERROR;
    }

    if ((size_t)g_in->bytes < kInputSamples)
    {
        LOG_E("Input bytes too small: %d", (int)g_in->bytes);
        return -RT_ERROR;
    }

    memcpy(g_in->data.int8, in_q, kInputSamples);

    if (g_interp->Invoke() != kTfLiteOk)
    {
        LOG_E("Invoke failed");
        return -RT_ERROR;
    }

    const int8_t out_raw = g_out->data.int8[0];
    const float score = ((int)out_raw - kOutZeroPoint) * kOutScale;

    const rt_tick_t now = rt_tick_get();
    const rt_bool_t cooldown_ok = (g_last_detect_tick == 0) ||
                                  ((now - g_last_detect_tick) >= rt_tick_from_millisecond(kDetectCooldownMs));

    const rt_bool_t detected = (score >= kMeowThreshold && cooldown_ok);

    if (detected)
    {
        g_last_detect_tick = now;
        LOG_W("MEOW DETECTED: score=%.3f (raw=%d) threshold=%.2f", score, (int)out_raw, kMeowThreshold);
    }
    else
    {
        LOG_I("NO MEOW: score=%.3f (raw=%d) threshold=%.2f%s",
              score, (int)out_raw, kMeowThreshold,
              (score >= kMeowThreshold && !cooldown_ok) ? " (cooldown)" : "");
    }

    if (out_score)
        *out_score = score;
    if (out_detected)
        *out_detected = detected;

    return RT_EOK;
#endif
}

#define MEOW_THREAD_STACK_SIZE 4096
#define MEOW_THREAD_PRIORITY   18
#define MEOW_THREAD_TICK       10

static void meow_detect_thread_entry(void *parameter)
{
    (void)parameter;

    LOG_I("meow: sliding window started (2s window, hop=%d samples)", (int)kHopSamples);

    if (init_model() != 0)
    {
        LOG_E("meow: init_model failed");
        g_meow_running = RT_FALSE;
        g_meow_tid = RT_NULL;
        return;
    }

    leds_init_once();
    led_write(kLedBlue, RT_FALSE);

    g_mic_dev = rt_device_find(BSP_XIAOZHI_MIC_DEVICE_NAME);
    if (!g_mic_dev)
    {
        LOG_E("meow: cannot find audio device '%s'", BSP_XIAOZHI_MIC_DEVICE_NAME);
        g_meow_running = RT_FALSE;
        g_meow_tid = RT_NULL;
        return;
    }

    if (rt_device_open(g_mic_dev, RT_DEVICE_FLAG_RDONLY) != RT_EOK)
    {
        LOG_E("meow: cannot open audio device");
        g_mic_dev = RT_NULL;
        g_meow_running = RT_FALSE;
        g_meow_tid = RT_NULL;
        return;
    }

    static int16_t ring[kInputSamples] rt_section(".m33_m55_shared_hyperram");
    static int16_t snap[kInputSamples] rt_section(".m33_m55_shared_hyperram");
    int16_t pdm_frame[PDM_FRAME_SAMPLES];
    size_t w = 0;
    size_t filled = 0;
    size_t since_last = 0;

    while (g_meow_running)
    {
        const rt_size_t read_size = rt_device_read(g_mic_dev, 0, pdm_frame, PDM_FRAME_SIZE);
        if (read_size == 0)
        {
            /* keep UI responsive and allow quick stop */
            rt_thread_mdelay(1);
            continue;
        }

        const size_t total_samples = read_size / sizeof(int16_t);
#if PDM_IS_STEREO
        const size_t mono_samples = total_samples / 2;
        for (size_t i = 0; i < mono_samples; i++)
        {
            ring[w] = pdm_frame[i * 2 + 1];
            w = (w + 1) % kInputSamples;
            if (filled < kInputSamples) filled++;
            since_last++;
        }
#else
        for (size_t i = 0; i < total_samples; i++)
        {
            ring[w] = pdm_frame[i];
            w = (w + 1) % kInputSamples;
            if (filled < kInputSamples) filled++;
            since_last++;
        }
#endif

        /* Non-blocking blue blink handling */
        const rt_tick_t now = rt_tick_get();
        if (g_blue_blink_until != 0 && now < g_blue_blink_until)
        {
            if (now >= g_blue_blink_next_toggle)
            {
                g_blue_blink_on = (g_blue_blink_on == RT_FALSE) ? RT_TRUE : RT_FALSE;
                led_write(kLedBlue, g_blue_blink_on);
                g_blue_blink_next_toggle = now + rt_tick_from_millisecond(50);
            }
        }
        else
        {
            g_blue_blink_until = 0;
            g_blue_blink_on = RT_FALSE;
            led_write(kLedBlue, RT_FALSE);
        }

        if (filled < kInputSamples)
            continue;

        if (since_last < kHopSamples)
            continue;

        since_last = 0;

        /* Snapshot last 2s from ring into linear buffer */
        size_t tail = w; /* w points to next write => oldest is w */
        const size_t n1 = kInputSamples - tail;
        memcpy(&snap[0], &ring[tail], n1 * sizeof(int16_t));
        if (tail != 0)
            memcpy(&snap[n1], &ring[0], tail * sizeof(int16_t));

        /* During "sampling+infer", keep blue off (unless blinking) */
        if (g_blue_blink_until == 0)
            led_write(kLedBlue, RT_FALSE);

        float score = 0.0f;
        rt_bool_t detected = RT_FALSE;
        int ret = meow_infer_from_pcm(snap, &score, &detected);
        if (ret != RT_EOK)
        {
            LOG_W("meow: infer failed (%d)", ret);
            continue;
        }

        xiaozhi_ui_set_meow_result(detected ? true : false, score);
        {
            const char *session_id = xz_ws_get_session_id();
            if (session_id && session_id[0] != '\0')
            {
                char meow_msg[160];
                rt_snprintf(meow_msg, sizeof(meow_msg),
                            "{\"session_id\":\"%s\",\"type\":\"meow\","
                            "\"score\":%.3f,\"is_cat\":%s,\"ts\":%u}",
                            session_id,
                            score,
                            detected ? "true" : "false",
                            (unsigned)rt_tick_get());
                (void)ws_send_text_locked(meow_msg);
            }
        }
        if (detected)
        {
            blue_blink_for_ms(1000, 100);
            meow_water_on_meow();
        }
    }

    if (g_mic_dev)
    {
        rt_device_close(g_mic_dev);
        g_mic_dev = RT_NULL;
    }

    LOG_I("meow: detect thread exiting");
    g_meow_tid = RT_NULL;
}

extern "C" {

int meow_detect_start(void)
{
#ifndef RT_USING_AUDIO
    LOG_E("RT_USING_AUDIO not enabled");
    return -RT_ERROR;
#else
    if (g_meow_running)
    {
        LOG_I("meow: detect already running");
        return RT_EOK;
    }

    if (init_model() != 0)
    {
        return -RT_ERROR;
    }

    leds_init_once();
    // Running: red off, green on, blue off
    led_write(kLedRed, RT_FALSE);
    led_write(kLedGreen, RT_TRUE);
    led_write(kLedBlue, RT_FALSE);

    g_meow_running = RT_TRUE;

    g_meow_tid = rt_thread_create("meow_det",
                                  meow_detect_thread_entry,
                                  RT_NULL,
                                  MEOW_THREAD_STACK_SIZE,
                                  MEOW_THREAD_PRIORITY,
                                  MEOW_THREAD_TICK);
    if (!g_meow_tid)
    {
        LOG_E("meow: create thread failed");
        g_meow_running = RT_FALSE;
        return -RT_ENOMEM;
    }

    rt_thread_startup(g_meow_tid);
    return RT_EOK;
#endif
}

int meow_detect_stop(void)
{
    /* Idempotent stop: always force LED state to "stopped" */
    g_meow_running = RT_FALSE;

    // Stopped: red on, green off, blue off
    leds_init_once();
    led_write(kLedRed, RT_TRUE);
    led_write(kLedGreen, RT_FALSE);
    led_write(kLedBlue, RT_FALSE);

    /* Give thread time to exit; no hard join API on RT-Thread */
    rt_thread_mdelay(100);
    return RT_EOK;
}

} // extern "C"

#ifdef RT_USING_FINSH
/*
 * Debug command: capture ~2s audio and infer once.
 * This is kept for manual testing via MSH and is independent of the sliding-window thread.
 */
static int meow_detect_once(void)
{
#ifndef RT_USING_AUDIO
    LOG_E("RT_USING_AUDIO not enabled");
    return -RT_ERROR;
#else
    if (init_model() != 0)
        return -RT_ERROR;

    rt_device_t dev = rt_device_find(BSP_XIAOZHI_MIC_DEVICE_NAME);
    if (!dev)
    {
        LOG_E("Cannot find audio device '%s'", BSP_XIAOZHI_MIC_DEVICE_NAME);
        return -RT_ERROR;
    }

    if (rt_device_open(dev, RT_DEVICE_FLAG_RDONLY) != RT_EOK)
    {
        LOG_E("Cannot open audio device");
        return -RT_ERROR;
    }

    static int16_t pcm[kInputSamples] rt_section(".m33_m55_shared_hyperram");
    int16_t pdm_frame[PDM_FRAME_SAMPLES];

    size_t collected = 0;
    while (collected < kInputSamples)
    {
        const rt_size_t read_size = rt_device_read(dev, 0, pdm_frame, PDM_FRAME_SIZE);
        if (read_size == 0)
        {
            rt_thread_mdelay(1);
            continue;
        }

        const size_t total_samples = read_size / sizeof(int16_t);
#if PDM_IS_STEREO
        const size_t mono_samples = total_samples / 2;
        for (size_t i = 0; i < mono_samples && collected < kInputSamples; i++)
        {
            pcm[collected++] = pdm_frame[i * 2 + 1]; // right channel
        }
#else
        for (size_t i = 0; i < total_samples && collected < kInputSamples; i++)
        {
            pcm[collected++] = pdm_frame[i];
        }
#endif
    }

    rt_device_close(dev);

    led_write(kLedBlue, RT_FALSE);

    float score = 0.0f;
    rt_bool_t detected = RT_FALSE;
    int ret = meow_infer_from_pcm(pcm, &score, &detected);
    if (ret != RT_EOK)
        return ret;

    xiaozhi_ui_set_meow_result(detected ? true : false, score);
    if (detected)
        blue_blink_for_ms(1000, 100);

    return RT_EOK;
#endif
}

MSH_CMD_EXPORT(meow_detect_once, Capture mic0 audio (32000 samples) and run meow model once);
#endif

