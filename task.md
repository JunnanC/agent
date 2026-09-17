# 本地开发环境 Task

## 文件清单

| 顺序 | 文件 | 动作 |
|---|---|---|
| 1 | `.gitignore` | 新增 |
| 2 | `.env.example` | 新增 |
| 3 | `docker-compose.yml` | 新增 |
| 4 | `backend/Dockerfile` | 新增 |
| 5 | `backend/pyproject.toml` | 新增 |
| 6 | `backend/.env.example` | 新增 |
| 7 | `backend/config/env.py` | 新增 |
| 8 | `backend/config/settings/base.py` | 新增 |
| 9 | `backend/config/settings/dev.py` | 新增 |
| 10 | `backend/config/settings/test.py` | 新增 |
| 11 | `backend/config/settings/prod.py` | 新增 |
| 12 | `backend/config/__init__.py` | 新增 |
| 13 | `backend/config/celery.py` | 新增 |
| 14 | `backend/config/urls.py` | 新增 |
| 15 | `backend/config/wsgi.py` | 新增 |
| 16 | `backend/config/asgi.py` | 新增 |
| 17 | `backend/apps/common/__init__.py` | 新增 |
| 18 | `backend/apps/common/apps.py` | 新增 |
| 19 | `backend/apps/common/constants.py` | 新增 |
| 20 | `backend/apps/common/health.py` | 新增 |
| 21 | `backend/apps/common/storage.py` | 新增 |
| 22 | `frontend/.env.example` | 新增 |
| 23 | `scripts/dev-up.sh` | 新增 |
| 24 | `scripts/dev-down.sh` | 新增 |
| 25 | `backend/README.md` | 新增 |

## 任务列表

### T1. 建立仓库级防护与公共配置

步骤：
1. 新增根 `.gitignore`，覆盖密钥、环境、Python、Node、本地设施与 IDE/OS 产物。
2. 确保 `.env.*` 忽略规则之后存在 `!.env.example`。
3. 新增根 `.env.example`，仅放置公共非敏感项。

验证：
- 运行 Git 检查确认 `.env` 被忽略、`.env.example` 不被忽略。
- 检查忽略规则覆盖任务要求的全部类别。

### T2. 建立后端工程骨架与配置读取

步骤：
1. 新增 `backend/Dockerfile`，基础镜像使用 Python 3.12。
2. 新增 `backend/pyproject.toml`，声明依赖与 ruff 配置。
3. 新增 `backend/.env.example`，覆盖 Django、MySQL、Redis、Celery、MinIO 与四个桶。
4. 新增 `backend/config/env.py`，集中读取并校验环境变量。
5. 拆分 `base.py`、`dev.py`、`test.py`、`prod.py`。
6. 新增 Celery、URL、WSGI、ASGI 入口。

验证：
- 在缺少必需环境变量时启动失败并输出明确错误。
- Celery broker/result 指向 Redis db 1，cache/lock 指向 db 0。
- `ruff format --check` 与 `ruff check` 通过。

### T3. 建立通用应用与健康检查

步骤：
1. 新增 `common` 应用基础结构。
2. 新增健康检查端点，检查 API、MySQL、Redis、MinIO。
3. 新增 MinIO 客户端封装，仅提供预签名 URL 能力，不代理文件正文。

验证：
- 调用 `GET /admin/health`，返回四个组件状态。
- 停止任一依赖后，对应组件状态变为不可用，但响应不泄露配置或堆栈。
- 使用预签名 URL 上传并下载一个小文件。

### T4. 建立 Compose 编排与对象存储初始化

步骤：
1. 新增 `docker-compose.yml`。
2. 配置 MySQL、Redis、MinIO、API、Worker、Beat。
3. 为基础服务配置命名卷和健康检查。
4. 新增一次性 MinIO 初始化服务，创建四个私有桶。
5. 添加 E3 Fake/Container Adapter 注释服务骨架。

验证：
- `docker compose config` 校验通过。
- 基础服务健康后，API、Worker、Beat 才启动。
- 四个桶均存在且私有。
- 停止后重新启动，数据卷中的数据仍存在。

### T5. 建立一键起停脚本

步骤：
1. 新增 `scripts/dev-up.sh`。
2. 新增 `scripts/dev-down.sh`。
3. 脚本自动检查并生成根、后端、前端 `.env`。
4. 启动脚本等待健康检查成功。

验证：
- 从未生成 `.env` 的状态执行 `dev-up.sh`，无需手工修改文件即可启动。
- 执行 `dev-down.sh` 后容器停止且数据卷保留。

### T6. 完善文档与前端环境示例

步骤：
1. 新增 `frontend/.env.example`。
2. 新增 `backend/README.md`，包含环境变量清单、启动方式、验证方式、设计决策。
3. 登记全部新增环境变量。

验证：
- README 变量清单与 `.env.example` 完全一致。
- 每项包含用途、必填性、默认值和影响范围。

### T7. 全量验收与修复

步骤：
1. 空环境启动验证。
2. MySQL 字符集、引擎与时区验证。
3. Celery 任务消费与 Redis db 隔离验证。
4. MinIO 四桶与预签名 URL 验证。
5. 必填环境变量缺失验证。
6. 敏感文件与 Git 状态验证。
7. ruff 检查。

验证：
- `spec.md` 与 `task.md` 的每条验收标准均有执行证据。
- 未通过的项修复后重新验证。

## 执行状态

| 任务 | 状态 |
|---|---|
| T1 | 已完成 |
| T2 | 已完成 |
| T3 | 已完成 |
| T4 | 已完成 |
| T5 | 已完成 |
| T6 | 已完成 |
| T7 | 已完成 |
