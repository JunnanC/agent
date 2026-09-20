# B6 · 契约生成与入口链路验收记录

生成时间：2026-09-20 17:07:34 +08:00

## 1. OpenAPI 契约

实际产物路径：`backend/openapi.json`

生成命令：

```powershell
$env:SECRET_KEY="local-check-secret"
$env:DJANGO_SETTINGS_MODULE="education_experiment_platform.settings.local"
python manage.py spectacular --format openapi-json --validate --file openapi.json
```

生成结果：

```text
Schema generation summary:
Warnings: 0
Errors: 0
```

契约元数据：

```json
{
  "title": "Education Experiment Platform API",
  "version": "2.0.0",
  "x-openapi-revision": "2026-09-20.b6-pending-freeze",
  "x-generated-at": "2026-09-20T17:07:29+08:00",
  "x-contract-status": "pending-freeze; replace after contract freeze"
}
```

### 端点清单与 tag

```text
/api/v2/events/stream                         GET    notifications
/api/v2/files/{asset_id}/download-grants      POST   core
/api/v2/tasks/{public_id}/workspace-sessions  POST   workspaces
/api/v2/tasks/{public_id}/workspace-snapshot  PUT    workspaces
/api/v2/workspace-sessions/{public_id}/renew  POST   workspaces
/api/v2/workspace-sessions/{public_id}/revoke POST   workspaces
/files/{one_time_token}                       GET    core
```

### 特殊端点处理

- `GET /api/v2/events/stream`：保留在 schema，响应描述明确为 `text/event-stream` 非 JSON；前端生成器必须排除并由 `event-client` 处理。
- `GET /files/{one_time_token}`：保留在 schema，响应描述明确为文件流非 JSON；不在 `/api/v2` 分区，前端生成器必须排除。
- `POST /internal/workspace-tokens/verify`：`exclude=True`，未出现在 public schema。
- `GET /health`：`exclude=True`，未出现在 public schema；该端点仅用于部署健康检查。
- `POST /api/v2/files/{asset_id}/download-grants`：保留在 schema，供前端生成请求函数。

人工 diff 结论：与 `DECISIONS.md` D-001/D-002/D-004 一致；不存在 `/events`、`/api/v2/files/{token}`、`/me/experiment-tasks` 回流路径。

## 2. 入口链路配置片段

实际落盘路径：

- `/api/v2/*`：`backend/deploy/01-api-v2.conf`
- `/api/v2/events/stream`：`backend/deploy/02-events-stream.conf`
- `/workspace/*`：USER 使用 `backend/deploy/03-workspace.conf`；TEACHING/PLATFORM 使用 `backend/deploy/03-workspace-reject.conf`
- `/files/*`：`backend/deploy/04-files.conf`
- 全局 `http{}`：`backend/deploy/00-http.conf`（只 include 一次，定义 `download_limit`）

说明：

- 四份片段均丢弃浏览器传入的 `X-Portal`，由可信 Host 在网关层重新映射。
- 全部透传 W3C `traceparent`、`X-Request-ID`。
- SSE 独立于通用 `/api/v2` 片段，关闭 buffering/cache/request buffering，长读超时且 `proxy_next_upstream off`。
- `/workspace/*` 仅 USER 站代理并携带 `Upgrade`/`Connection`；TEACHING/PLATFORM 站直接返回 404。
- `/files/*` 仅代理 Django，不代理对象存储；隐藏对象存储相关响应头并配置限速。


### `/api/v2/*`：`backend/deploy/01-api-v2.conf`

```nginx
# Nginx -> API Gateway -> Django fragment for /api/v2.
# Include this location in all three portal server blocks.

location /api/v2/ {
    client_max_body_size 25m;

    proxy_pass http://api_gateway;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # The gateway is the only component allowed to derive X-Portal from Host.
    proxy_set_header X-Portal "";
    proxy_set_header X-Request-ID $request_id;
    proxy_set_header traceparent $http_traceparent;

    proxy_connect_timeout 3s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
    proxy_next_upstream off;

    proxy_hide_header Cache-Control;
    add_header Cache-Control "private, no-store" always;
}
```

### `/api/v2/events/stream`：`backend/deploy/02-events-stream.conf`

```nginx
# Nginx -> API Gateway -> Django fragment for SSE.
# Include before the generic /api/v2/ location.

location = /api/v2/events/stream {
    proxy_pass http://api_gateway;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Drop browser-supplied portal; the gateway derives it from trusted Host.
    proxy_set_header X-Portal "";
    proxy_set_header X-Request-ID $request_id;
    proxy_set_header traceparent $http_traceparent;
    proxy_set_header Last-Event-ID $http_last_event_id;

    proxy_buffering off;
    proxy_cache off;
    proxy_request_buffering off;
    proxy_read_timeout 1h;
    proxy_send_timeout 1h;
    proxy_next_upstream off;

    proxy_hide_header Cache-Control;
    add_header Cache-Control "no-cache, no-transform" always;
    add_header X-Accel-Buffering no always;
}
```

### `/workspace/*`：`backend/deploy/03-workspace.conf`

```nginx
# USER portal server block: proxy to the workspace gateway with Upgrade.

location /workspace/ {
    proxy_pass http://workspace_gateway;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;

    # Drop browser-supplied portal; only the gateway may set it from Host.
    proxy_set_header X-Portal "";
    proxy_set_header X-Request-ID $request_id;
    proxy_set_header traceparent $http_traceparent;

    proxy_connect_timeout 3s;
    proxy_send_timeout 15m;
    proxy_read_timeout 15m;
    proxy_next_upstream off;

    proxy_hide_header Cache-Control;
    add_header Cache-Control "private, no-store" always;
}

# TEACHING and PLATFORM portal server blocks: reject student-workspace access.

location /workspace/ {
    return 404;
}
```

### `/workspace/*` rejection：`backend/deploy/03-workspace-reject.conf`

```nginx
# TEACHING and PLATFORM portal server blocks: reject student-workspace access.

location /workspace/ {
    return 404;
}
```

### `/files/*`：`backend/deploy/04-files.conf`

先在 `nginx.conf` 的 `http{}` 上下文 include 全局片段（只 include 一次）：

```nginx
# nginx.conf http{} context
include backend/deploy/00-http.conf;
```

`00-http.conf` 定义 `/files/*` 依赖的限流共享内存区和 WebSocket `Connection` 映射：

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

limit_req_zone $binary_remote_addr zone=download_limit:10m rate=10r/s;
```

`api_gateway` 与 `workspace_gateway` 是外部部署依赖，必须在主 `nginx.conf` 的 `http{}` 上下文中定义：

```nginx
upstream api_gateway { server <api-gateway-host:port>; }
upstream workspace_gateway { server <workspace-gateway-host:port>; }
```

```nginx
# Nginx -> API Gateway -> Django fragment for one-time-token downloads.
# Include this location in all three portal server blocks.

location /files/ {
    limit_req zone=download_limit burst=10 nodelay;

    proxy_pass http://api_gateway;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    # Drop browser-supplied portal; the gateway derives it from trusted Host.
    proxy_set_header X-Portal "";
    proxy_set_header X-Request-ID $request_id;
    proxy_set_header traceparent $http_traceparent;

    proxy_connect_timeout 3s;
    proxy_send_timeout 10m;
    proxy_read_timeout 10m;
    proxy_next_upstream off;

    # Django is the download authority. Nginx never proxies object storage.
    proxy_hide_header Cache-Control;
    proxy_hide_header Location;
    proxy_hide_header X-Amz-Bucket;
    proxy_hide_header X-Amz-Endpoint;
    add_header Cache-Control "private, no-store" always;
}
```
## 3. 今日链路验收

结论：**BLOCKED: 依赖部署层环境**。

原因：当前仓库没有可运行的 Nginx、API Gateway、Gateway Host 映射和预发布部署环境。按 `06:63` 与 B3 的同一口径，不得用 Django 直连结果替代链路证据，也不得声称验收通过。

待部署切片完成后，经统一入口 `https://user.example.edu` 补验：

| 编号 | 状态 | 补验命令 |
|---|---|---|
| K-01 | BLOCKED: 依赖部署层环境 | `curl -N -i https://user.example.edu/api/v2/events/stream` |
| K-02 | BLOCKED: 依赖部署层环境 | 断开 SSE 后重连，同时检查网关 retry/upstream 日志 |
| K-03 | BLOCKED: 依赖部署层环境 | `curl -i https://user.example.edu/api/v2/events/stream` |
| K-04 | BLOCKED: 依赖部署层环境 | `curl -i https://teacher.example.edu/workspace/test` |
| K-05 | BLOCKED: 依赖部署层环境 | `curl -i -H "Connection: Upgrade" -H "Upgrade: websocket" https://user.example.edu/workspace/test` |
| K-06 | BLOCKED: 依赖部署层环境 | `curl -i https://user.example.edu/files/<one_time_token>`，同 token 二次请求必须失败 |
| K-07 | BLOCKED: 依赖部署层环境 | `curl -i -H "traceparent: 00-<trace-id>-<span-id>-01" https://user.example.edu/api/v2/not-exist` |
| K-08 | BLOCKED: 依赖部署层环境 | 分别访问 `/events`、`/api/v2/files/<token>`、`/me/experiment-tasks` |
| K-09 | BLOCKED: 依赖部署层环境 | `curl -i https://user.example.edu/health` 与 `curl -i https://user.example.edu/internal/workspace-tokens/verify` |

## 4. 链路命令输出证据

未执行 K-01~K-09：当前无 Nginx/API Gateway/预发布入口。为避免用直连 Django 输出伪造链路证据，所有命令均无终端输出，状态为 BLOCKED: 依赖部署层环境。

## 5. 测试证据

命令：

```powershell
python manage.py test
```

原始输出：

```text
......................
----------------------------------------------------------------------
Ran 22 tests in 0.040s

OK
Found 22 test(s).
System check identified no issues (0 silenced).
```

该测试仅证明 Django 路由与单元/集成行为，不证明 Nginx → Gateway → Django 链路。
契约关键断言：

```text
openapi=3.0.3
revision=2026-09-20.b6-pending-freeze
generated=2026-09-20T17:07:29+08:00
events_tags=notifications
files_tags=core
grant_tags=core
internal_present=False
paths=8
```

## 6. OPEN 汇总（B1~B6）

| 项 | 来源 | 状态 | V00 闸门 |
|---|---|---|---|
| requirements 未形成全量锁定 | B1 | OPEN | 是 |
| Django BigAutoField signed BIGINT 与 DDL BIGINT UNSIGNED 差异 | B1 / OPEN-DB-07 | OPEN | 是 |
| API Gateway 选型（APISIX/Kong/Traefik）未定 | 架构 V00 | OPEN | 是 |
| 是否由 Nginx 终止 TLS 未定 | 架构 V00 | OPEN | 是 |
| Workspace token 签名、轮换、密钥托管未定义 | B4 | OPEN | 是 |
| Workspace token 业务 TTL 常量未定义 | B4 | OPEN | 是 |
| Workspace 持久化模型与迁移未完成 | B4 | OPEN | 否 |
| 下载授权、MinIO 适配与持久化模型未完成 | B5 | OPEN | 否 |
| K-01~K-09 真实链路验收未完成 | B6 | BLOCKED: 依赖部署层环境 | 是 |

## 7. 今日未完成项

1. K-01~K-09：全部 `BLOCKED: 依赖部署层环境`，未用直连 Django 输出替代。
2. Nginx 与 API Gateway 尚未实际部署，`backend/deploy/*.conf` 只是配置骨架。
3. OpenAPI 产物为 `pending-freeze`，契约冻结后必须替换。
4. B4/B5 的持久化与真实对象存储适配仍未完成。
5. 临时验证代码：无；未引入临时验证文件。






