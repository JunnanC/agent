# 后端契约脚本 · B1~B9 代码改动说明

> **用途**：说明本人在各后端切片中修改的代码内容与对外契约，供团队对接、防撞车核对与后续切片复用。
> **责任人**：甘德富（后端 1）
> **数据来源**：`agent` 嵌套仓库 git 提交记录（逐条核对，非估算）
> **生成日期**：2026-09-21

---

## 0. 总览

| 切片 | 名称 | 提交 | 日期 | 改动量 |
|---|---|---|---|---|
| B1 | 工程底座与 AppConfig 骨架 | `e956e62` | 09-20 | 13 app 骨架 + 4 个根文件 |
| B2 + B5 | 学生端口功能路由骨架（含受控下载落地） | `ec7c3cd` | 09-20 | 16 files, +434 / -13 |
| B3 + B4 | SSE / workspace / files 路由骨架 | `ddb372b` | 09-20 | 33 files, +2207 / -81 |
| B6 | 契约生成与入口链路验收 | `49d47e5` + `466ff63` | 09-20 | 22 files, +1315 / -342 |
| B7 | trace / 结构化日志接入 | `8eb91b4` | 09-21 | 9 files, +763 / -26 |
| B8 | 测试夹具工厂 | `f0fd9a9` | 09-21 | 10 files, +347 / -141 |
| B9 | 受控下载幂等与限流收尾 | `0825964` | 09-21 | 8 files, +632 / -42 |

**说明**：B1~B9 的提交均落在同一条提交链上，`download-grants` 端点由 `git log -S` 定位确认首次出现于 `ec7c3cd`，即 B5 的核心产出合并在「学生端口功能路由骨架」提交中，无独立提交。

---

## 1. B1 · 工程底座与 AppConfig 骨架（`e956e62`）

**改动文件**

| 文件 | 动作 | 行数 |
|---|---|---|
| `backend/README.md` | 新增 | +17 |
| `backend/COMPATIBILITY.md` | 新增 | +35 |
| `backend/.env.example` | 新增 | +14 |
| `backend/.gitignore` | 新增 | +8 |
| `apps/__init__.py` + 13 个 app 的骨架目录 | 新增 | 每 app `apps.py` +11，其余占位 +1 |

**做了什么**

- 建立 Django 工程底座：项目根为 `backend/`（`manage.py` 在此），配置包 `education_experiment_platform/`，采用分包式 `settings/{base,local,test,integration,prod}.py`。
- 建立 **13 个领域 app** 的 AppConfig 与统一目录布局：`core / accounts / courses / labtemplates / experiments / provisioning / workspaces / reports / reviews / archives / agents / governance / notifications`。
- 每个 app 统一具备：`adapters / apps / events / migrations / models / permissions / ports / selectors / serializers / services / tasks / tests / urls / views`。
- 记录技术基线事实源（语言、Django、DRF、drf-spectacular 版本）。

**对外契约**：无 HTTP 端点。确立边界约定 —— **不存在按端划分的 app**，学生是 `USER` portal 的准入维度而非领域边界，禁止创建 `student` / `teacher` / `platform` / `teams`。

---

## 2. B2 + B5 · 学生端口功能路由骨架（`ec7c3cd`，16 files, +434 / -13）

**改动文件**

| 文件 | 动作 | 行数 |
|---|---|---|
| `apps/core/http.py` | 新增 | +47 |
| `apps/core/views.py` | 修改 | +38 |
| `apps/core/middleware.py` | 修改 | +33 |
| `apps/core/urls.py` | 修改 | +14 |
| `apps/core/management/commands/list_urls.py` | 新增 | +34 |
| `apps/core/tests/test_b2_routes.py` | 新增 | +91 |
| `apps/notifications/urls.py`、`views.py` | 修改 | +10 / +15 |
| `apps/workspaces/views.py` | 修改 | +80 |
| `apps/workspaces/urls.py` | 修改 | +35 |
| `apps/workspaces/serializers.py` | 修改 | +17 |
| `apps/workspaces/internal_urls.py` | 新增 | +13 |
| `education_experiment_platform/urls.py` | 新增 | +10 |
| `education_experiment_platform/api_urls.py` | 修改 | +8 |

**做了什么**

- 建立三层路由分层：顶层 `urls.py`（`/health`、`/api/v2`、`/internal`）→ `api_urls.py` → 各 app `urls.py`。
- **`download-grants` 端点在本提交落地**（B5 核心）：由 501 占位升级为真实响应。
- 新增 `core/http.py`：统一错误信封基础设施。
- 新增 `list_urls.py` 管理命令：路由自查。

**对外契约**

- `POST /api/v2/files/{asset_id}/download-grants` → `201`，响应体 `{asset_id, one_time_token, expires_at, max_uses}`。

---

## 3. B3 + B4 · SSE / workspace / files 路由骨架（`ddb372b`，33 files, +2207 / -81）

**改动文件（新世界）**

| 文件 | 动作 | 行数 |
|---|---|---|
| `apps/workspaces/services.py` | 新增 | +154 |
| `apps/workspaces/views.py` | 修改 | +174 |
| `apps/workspaces/adapters/fake.py` | 新增 | +205 |
| `apps/workspaces/ports.py` | 修改 | +60 |
| `apps/workspaces/serializers.py` | 修改 | +58 |
| `apps/workspaces/urls.py` | 修改 | +19 |
| `apps/workspaces/tests/test_b4_workspaces.py` | 新增 | +142 |
| `apps/workspaces/OPEN.md` | 新增 | +13 |
| `apps/notifications/events.py` | 修改 | +132 |
| `apps/notifications/views.py` | 修改 | +83 |
| `apps/notifications/ports.py` | 修改 | +38 |
| `apps/notifications/adapters/fake.py` | 新增 | +52 |
| `apps/notifications/tests/test_b3_events.py` | 新增 | +144 |
| `backend/openapi.json` | 修改 | +289 |

**改动文件（`program/` 遗留树）**

`program/core/` 下 `services.py` +152、`views.py` +103、`http.py` +54、`ports.py` +59、`adapters/fake.py` +99、`response/error.py` +28、`tests/test_b5_downloads.py` +131 等。

> **注意**：`program/` 为早期布局残留，`INSTALLED_APPS` 未加载任何 `program.*`。B9 已定论 —— **不迁移、不删除**，整树去留与 `exchange()` 迁移一并移交 B10。

**对外契约**

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/v2/events/stream` | GET | SSE 事件流，非 JSON 响应 |
| `/api/v2/tasks/{public_id}/workspace-sessions` | POST | 工作区会话创建 |
| `/api/v2/tasks/{public_id}/workspace-snapshot` | GET | 工作区快照 |
| `/api/v2/workspace-sessions/{public_id}/renew` | POST | 续期 |
| `/api/v2/workspace-sessions/{public_id}/revoke` | POST | 撤销 |
| `/files/{one_time_token}` | GET | 文件下载，当前 501 占位 |
| `/internal/workspace-tokens/verify` | POST | **内部端点，不进 public schema** |

---

## 4. B6 · 契约生成与入口链路验收（`49d47e5` + `466ff63`）

**改动文件**

| 文件 | 动作 | 行数 |
|---|---|---|
| `backend/B6_ACCEPTANCE.md` | 新增 | +291，后 +42 |
| `backend/openapi.json` | 修改 | +750 / -295，后 +103 |
| `apps/core/views.py` | 修改 | +20，后 +85 |
| `apps/core/adapters/fake.py` | 修改 | +148 |
| `apps/core/serializers.py` | 修改 | +17 |
| `apps/core/urls.py` | 修改 | +4 |
| `apps/notifications/views.py` | 修改 | +16 |
| `apps/workspaces/views.py` | 修改 | +4 |
| `deploy/01-api-v2.conf` | 新增 | +25 |
| `deploy/02-events-stream.conf` | 新增 | +27 |
| `deploy/03-workspace.conf` | 新增 | +30，后 +8 |
| `deploy/03-workspace-reject.conf` | 新增 | +5 |
| `deploy/04-files.conf` | 新增 | +29，后 +1 |
| `deploy/00-http.conf` | 修改 | +10 |
| `settings/base.py` | 修改 | +6 |
| `apps/core/tests/test_b2_routes.py` | 修改 | +34 |

**做了什么**

- 配置 drf-spectacular，产出 OpenAPI 3.0.3 契约 `backend/openapi.json`，tag 一律取限界上下文（app）名。
- 落盘四份网关配置片段（`/api/v2`、`events/stream`、`/workspace`、`/files`）。
- 按 B6 要求处理非标准端点：SSE 与 `/files/{token}` 标注非 JSON 响应，内部端点 `workspace-tokens/verify` 排除出 public schema。

**OPEN / BLOCKED**

- K-01~K-09 网关链路验收因部署环境未就绪，整体标注 `BLOCKED: 依赖部署层环境`，未以直连 Django 的输出代替链路证据。

---

## 5. B7 · trace / 结构化日志接入（`8eb91b4`，9 files, +763 / -26）

**改动文件**

| 文件 | 动作 | 行数 |
|---|---|---|
| `apps/core/logging.py` | 新增 | +126 |
| `apps/core/tracing.py` | 新增 | +60 |
| `apps/core/middleware.py` | 修改 | +62 / -26 |
| `apps/core/schema.py` | 修改 | +17 |
| `apps/core/tests/test_b7_tracing.py` | 新增 | +299 |
| `apps/membership/blocking.py` | 新增 | +82 ⚠️ |
| `education_experiment_platform/celery.py` | 修改 | +32 |
| `education_experiment_platform/settings/base.py` | 修改 | +41 |
| `backend/openapi.json` | 修改 | +70 |

**做了什么**

- 新增 `tracing.py`：W3C trace context（traceparent）解析与 contextvars 绑定。
- 新增 `logging.py`：结构化 JSON 日志，字段名定稿（`duration_ms` 数值毫秒等），后续切片沿用，不得另造同义字段。
- `middleware.py`：补 contextvars 绑定与清理；**修正** trace_id 形态为 `uuid4().hex`（32 位小写十六进制），与 W3C trace-id 对齐（原缺失 traceparent 时生成带连字符 uuid，形态不一致）。
- `schema.py`：经 drf-spectacular postprocess hook 新增 `X-Trace-Id` 响应头。
- `celery.py`：Celery 侧 trace 传递。

**对外契约**

- 错误信封 `{code, message, details, trace_id}` 形状 **保持不变**，本切片对信封不动。
- 新增响应头 `X-Trace-Id`（成功路径首次获得 trace 信息）。
- 成功响应体不补 `trace_id`。

**⚠️ 待处理**：`apps/membership/blocking.py` 文件内混入了 shell 命令文本（`git remote -v`、`git branch -a`），会导致 `SyntaxError`；且其 `import` 的 `constants.py` 不存在。该文件当前未进 `INSTALLED_APPS`，故未影响测试，但属落盘污染，需修复或移除。`membership` 亦不在 B1 的 13 个领域 app 名单内，归属待确认。

---

## 6. B8 · 测试夹具工厂（`f0fd9a9`，10 files, +347 / -141）

**改动文件**

| 文件 | 动作 | 行数 |
|---|---|---|
| `apps/core/testing/__init__.py` | 新增 | +23 |
| `apps/core/testing/assertions.py` | 新增 | +109 |
| `apps/core/testing/cases.py` | 新增 | +13 |
| `apps/core/testing/ids.py` | 新增 | +8 |
| `apps/core/testing/tracing.py` | 新增 | +49 |
| `apps/core/tests/test_b8_testing_factory.py` | 新增 | +139 |
| `apps/core/tests/test_b2_routes.py` | 修改 | +7 |
| `apps/notifications/tests/test_b3_events.py` | 修改 | +6 |
| `apps/workspaces/tests/test_b4_workspaces.py` | 修改 | +3 |
| `program/core/tests/test_b5_downloads.py` | **删除** | -131 |

**做了什么**

- 建立统一测试夹具工厂 `apps/core/testing/`：`ids`（标识生成）、`tracing`（trace 断言）、`assertions`（通用断言）、`cases`（测试基类）。
- B5 测试从 `program/` 遗留树迁移进 Django 测试体系，删除 `program/core/tests/test_b5_downloads.py`。
- 既有 B2/B3/B4 测试改为复用工厂，消除重复工具。

**对外契约**：测试工厂为内部工具，无 HTTP 契约。后续切片（B9 已复用）应优先复用，不得另起一套同义工具。

---

## 7. B9 · 受控下载幂等与限流收尾（`0825964`，8 files, +632 / -42）

**改动文件**

| 文件 | 动作 | 行数 |
|---|---|---|
| `apps/core/views.py` | 修改 | +120 |
| `apps/core/adapters/fake.py` | 修改 | +181 |
| `apps/core/http.py` | 修改 | +13 |
| `apps/core/serializers.py` | 修改 | +7 |
| `apps/core/tests/test_b9_idempotency.py` | 新增 | +214 |
| `deploy/00-http.conf` | 修改 | +1 |
| `deploy/01-api-v2.conf` | 修改 | +5 |
| `backend/openapi.json` | 修改 | +133 |

**做了什么**

- 幂等去重：按 `(actor_user_id, idempotency_key)` **复合作用域**去重，重复请求回放首次响应；参数或门户不同返回 `409`。含 key 长度校验与内存饱和防护、120s TTL、原子查写。
- 错误契约补全：统一错误信封 serializer，新增 400/403/404/409/429 分支。
- 限流：`00-http.conf` 新增独立 `api_write_limit` zone；`01-api-v2.conf` 用嵌套 location **仅**命中 `download-grants`，避免误伤同 location 下的 SSE 事件流。

**对外契约**

- `POST /api/v2/files/{asset_id}/download-grants`：**强制** `Idempotency-Key` 请求头；幂等重放时返回 `X-Idempotent-Replay` 响应头；契约声明 201/400/403/404/409/429。

**归属声明**：本切片不在原分配的四项任务（B1 / B3+B4+B5 / B7 / B8）之内，属额外补充，用于结清 B5 升级 201 后当场产生的欠债。**归属待项目经理确认；若已另行分配给其他同学，本人可将改动面交出，避免重复实现。**

---

## 8. 协作边界与防撞车提示

**本人占用的高冲突共享文件**（他人修改前请先沟通）：

| 文件 | 切片 | 风险 |
|---|---|---|
| `deploy/*.conf`（`00-http`、`01-api-v2`、`02-events-stream`、`03-workspace*`、`04-files`） | B6、B9 | nginx 配置，跨运维线，最易撞车 |
| `apps/core/views.py` | B2/B5、B6、B9 | core 为公共 ly，多切片共用 |
| `apps/core/adapters/fake.py` | B6、B9 | Fake 适配器集中地 |
| `backend/openapi.json` | B3/B4、B6、B7、B9 | 生成物，易产生合并冲突 |
| `education_experiment_platform/settings/base.py` | B6、B7 | 全局配置 |
| `education_experiment_platform/celery.py` | B7 | Celery 运行时 |

**未占用 / 未改动**

- `program/` 遗留树：B9 定论 **不迁移、不删除**，处置权移交 B10。
- `requirements.txt`：B9 明确未改动。
- `apps/membership/`：仅 B7 落了一个受污染文件，未完成，他人可接管。

---

## 9. OPEN 与遗留项

| # | 项 | 状态 |
|---|---|---|
| 1 | 幂等快照持明文令牌 | 仅限「独立仓库 + 120s TTL + 纯内存」四条件下放行；接 Redis/MySQL 后须改为加密快照或引用重放 |
| 2 | `GET /files/{one_time_token}` | 501 契约待 B10 定稿后补充 |
| 3 | 按 IP 限流 | 可能误伤 NAT 出口，接认证后应改为按主体限流 |
| 4 | `IDEMPOTENCY_STORE_SATURATED` 与 Nginx 429 语义重叠 | 待 V00 拍板 |
| 5 | `program/` 与 `exchange()` 迁移时机 | 移交 B10 |
| 6 | 测试工厂 pytest 双入口 | 暂不提供 |
| 7 | `apps/membership/blocking.py` 语法污染 | **待修复**，归属待确认 |
| 8 | `nginx -t` 校验 | 本机无 nginx 命令，未执行 |
