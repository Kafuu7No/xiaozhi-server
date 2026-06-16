#ifndef ENV_WS_UPLOADER_H
#define ENV_WS_UPLOADER_H

#include <rtthread.h>

#ifdef __cplusplus
extern "C" {
#endif

rt_err_t env_ws_uploader_start(rt_uint32_t period_ms);
rt_err_t env_read_once(float *temp_c, float *humi_rh);

rt_bool_t ws_send_text_locked(const char *msg);
const char *xz_ws_get_session_id(void);

#ifdef __cplusplus
}
#endif

#endif /* ENV_WS_UPLOADER_H */
