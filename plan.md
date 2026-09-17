# 本地开发环境 Plan

## 技术决策

- 运行环境统一使用 Python 3.12 镜像；代码兼容性下限为 Python 3.11+，本地不再使用 Python 3.14 作为开发运行时。
- 统一使用 Docker Compose 启动依赖与应用，避免依赖开发者本机安装 MySQL、Redis、MinIO、Python 3.12 或 Celery。
- 格式化与检查分别使用 `ruff format` 与 `ruff check`，不引入 black。
- MySQL、Redis、MinIO 职责固定：MySQL 只存业务事实；Redis 只存缓存、锁、限流、短期会话状态、幂等记录与队列；对象正文只存 MinIO。
- Django 不拥有数据库表结构；本阶段不生成 migration。
- 生产部署不在本阶段范围内，仅提供本地开发环境。

## 架构概览

```text
Docker Compose
├── mysql:8.0          业务事实存储，utf8mb4 / InnoDB / UTC
├── redis:7            db 0: 缓存、锁、限流、短期状态、幂等；db 1: Celery
├── minio              对象正文存储，四个私有桶
├── api                Django + DRF，提供 /admin/health
├── worker             Celery worker，连接 Redis db 1
├── beat               Celery beat，连接 Redis db 1
└── minio-init         一次性 mc 容器，创建私有桶后退出
```

API、Worker、Beat 使用同一后端镜像，并通过 `depends_on` 的 `service_healthy` 等待 MySQL、Redis、MinIO 健康。E3 的 Fake/Container Adapter 仅保留注释掉的服务骨架。

## 文件结构

```text
docker-compose.yml
.gitignore
.env.example
backend/
├── .env.example
├── README.md
├── Dockerfile
├── pyproject.toml
├── config/
│   ├── env.py
│   ├── __init__.py
│   ├── celery.py
│   ├── urls.py
│   ├── wsgi.py
│   ├── asgi.py
│   └── settings/
│       ├── base.py
│       ├── dev.py
│       ├── test.py
│       └── prod.py
└── apps/
    └── common/
        ├── __init__.py
        ├── apps.py
        ├── constants.py
        ├── health.py
        └── storage.py
frontend/
└── .env.example
scripts/
├── dev-up.sh
└── dev-down.sh
```

现有 `backend/education_experiment_platform` 目录仅作为历史结构存在，不作为新配置入口；新工程入口统一收敛到 `backend/config`。

## 配置设计

- `backend/config/env.py` 是环境变量唯一读取点，负责必填校验、类型转换、布尔解析和 URL 拼接。
- 必填变量缺失时抛出明确配置错误并阻止启动；不允许使用占位值静默降级。
- `settings/base.py` 提供通用配置；`dev.py` 面向本地容器；`test.py` 面向自动化测试；`prod.py` 只读取生产必需的环境差异值。
- `REDIS_CACHE_URL` 指向 Redis db 0；`CELERY_BROKER_URL` 与 result backend 指向 db 1。
- MinIO endpoint、访问凭据和四个桶名全部来自环境变量；业务代码只引用集中配置，不散落桶名。

## Compose 设计

- MySQL：
  - 镜像 `mysql:8.0`
  - 字符集 `utf8mb4`，排序规则 `utf8mb4_0900_ai_ci`
  - 命名卷持久化
  - healthcheck 使用 `mysqladmin ping`
  - 连接参数显式指定 UTC
- Redis：
  - 镜像 `redis:7`
  - 开启 AOF
  - 命名卷持久化
  - healthcheck 使用 `redis-cli ping`
- MinIO：
  - API 端口与控制台端口分离
  - 数据命名卷持久化
  - healthcheck 使用 MinIO 就绪探测
- MinIO 初始化：
  - 一次性 `minio/mc` 容器
  - 创建普通文件、实验成果与归档、运行时快照、导出物四个桶
  - 桶均设置为私有
  - 执行完成后退出

## 健康检查设计

- 路由：`GET /admin/health`
- 返回信息仅包含服务名与状态，例如 `api`、`mysql`、`redis`、`minio` 的 `up/down`。
- 不返回连接串、账号、桶名、内部地址、异常堆栈或配置值。
- 检查只读，不创建、修改或删除任何数据。

## 启动脚本设计

- `scripts/dev-up.sh`：
  - 检查根 `.env` 是否存在，不存在则从 `.env.example` 复制
  - 检查后端与前端 `.env` 是否存在，不存在则从对应示例复制
  - 使用 Docker Compose 构建并启动全部服务
  - 等待 API 健康检查成功后输出访问地址
- `scripts/dev-down.sh`：
  - 停止并移除容器与网络
  - 默认保留数据卷，避免误删本地数据

## 验证策略

- 使用 Compose 启动完整环境并访问 `/admin/health`。
- 进入 MySQL 容器验证字符集、引擎和 UTC。
- 触发一个 Celery 任务并确认 Worker 消费成功；分别清理 Redis db 0 后验证 db 1 队列仍可用。
- 使用 MinIO 预签名 URL 完成一次小文件上传和下载。
- 删除一个必需环境变量并确认应用启动失败。
- 运行 `ruff format --check` 与 `ruff check`。
- 扫描工作区确认不存在 `.env` 实际文件、密钥和证书。

## 明确不做

- 不实现业务模块、权限系统、业务 API 或前端页面。
- 不实现 Fake/Container Adapter 逻辑。
- 不修改数据库表结构。
- 不引入 PostgreSQL、Kubernetes、FastAPI、RQ/Arq、WebSocket 或云厂商运行时。
- 不提供生产编排或历史重写方案。
