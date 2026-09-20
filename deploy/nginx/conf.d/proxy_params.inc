# 通用代理参数 —— 被 nginx.conf 通过 include 引用
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Connection        "";
proxy_http_version 1.1;

# SSE 支持（实验事件流）
proxy_buffering off;
proxy_cache off;
proxy_read_timeout 3600s;
proxy_send_timeout 3600s;

# 超时
proxy_connect_timeout 10s;
proxy_next_upstream error timeout http_502 http_503;
proxy_next_upstream_tries 2;
