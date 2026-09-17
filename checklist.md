# 本地开发环境 Checklist

> 每一项通过运行代码或观察行为来验证，聚焦系统行为。

## 实现完整性

- [x] F1 六个服务由 Compose 定义并可启动（验证：`docker compose config` 通过并观察服务列表）
- [x] F1 API、Worker、Beat 依赖 MySQL、Redis、MinIO 的健康状态（验证：读取 `docker compose config` 中 `depends_on.condition=service_healthy`）
- [x] F1 基础服务使用命名卷持久化（验证：`docker compose config --volumes` 输出 MySQL、Redis、MinIO 卷）
- [x] F2 MySQL 使用 utf8mb4、InnoDB 与 UTC 连接（验证：查询 `character_set_database`、`@@time_zone` 与表引擎）
- [x] F3 Redis 开启 AOF（验证：检查 Redis 配置或 `CONFIG GET appendonly`）
- [x] F3 Redis db 0 与 db 1 职责隔离（验证：Django cache 指向 db 0，Celery broker/result 指向 db 1）
- [x] F4 MinIO API 与控制台端口分离（验证：分别访问 API 与控制台地址）
- [x] F4 四个桶由一次性初始化容器创建（验证：`mc ls` 或等价命令输出四个桶）
- [x] F4 四个桶均为私有（验证：匿名访问桶列表失败，认证访问成功）
- [x] F5 预签名 URL 可上传并下载小文件（验证：使用生成的预签名 URL 执行 PUT 和 GET）
- [x] F5 业务 API 不代理文件内容（验证：健康检查和现有公开路由均不返回对象正文）
- [x] F6 Django settings 拆分为 base/dev/test/prod（验证：检查四个配置模块均可被导入）
- [x] F6 环境变量集中读取并做必填校验（验证：删除任一必需变量后启动失败）
- [x] F7 三份 `.env.example` 均存在且逐项有注释（验证：检查文件内容）
- [x] F8 `.env` 被忽略而 `.env.example` 不被忽略（验证：`git check-ignore`）
- [x] F9 `GET /admin/health` 返回 API 与三个依赖的状态（验证：HTTP 请求观察 JSON）
- [x] F9 健康检查不泄露凭据、内部地址和堆栈（验证：检查成功与失败响应体）
- [x] F10 `dev-up.sh` 可一键启动并等待健康（验证：脚本执行后访问健康端点）
- [x] F10 `dev-down.sh` 可停止环境且保留数据卷（验证：停止后检查卷仍存在）
- [x] F10 E3 服务骨架仅以注释形式存在（验证：检查 Compose 文件）
- [x] F11 README 环境变量清单与示例文件一致（验证：逐项对比变量名、必填性、默认值）

## 集成

- [x] Worker 使用与 API 相同的环境配置（验证：启动日志加载 `config.settings.dev`）
- [x] Beat 使用与 API 相同的环境配置（验证：启动日志加载 `config.settings.dev`）
- [x] MinIO 初始化容器与 API 使用同一套桶名环境变量（验证：比较 Compose 环境配置）
- [x] MySQL、Redis、MinIO 健康后应用服务才启动（验证：首次冷启动日志观察启动顺序）

## 编译与测试

- [x] 后端容器可构建（验证：`docker compose build api`）
- [x] 后端容器可启动（验证：`docker compose up api` 后健康端点可访问）
- [x] Celery Worker 可启动（验证：`celery -A config worker` 启动日志无错误）
- [x] Celery Beat 可启动（验证：`celery -A config beat` 启动日志无错误）
- [x] `ruff format --check` 通过（验证：运行命令并查看退出码）
- [x] `ruff check` 通过（验证：运行命令并查看退出码）

## 端到端场景

- [x] 场景 1：空机器克隆 → 复制 `.env.example` → 执行 `scripts/dev-up.sh` → API、Worker、Beat 启动，`/admin/health` 返回全部 `up`（验证：完整执行流程）
- [x] 场景 2：清理 Redis db 0 → db 1 中的 Celery 队列仍可消费（验证：发布测试任务并观察 Worker 完成结果）
- [x] 场景 3：停止 MinIO → 健康检查显示 MinIO `down`，但不暴露内部地址、凭据或堆栈（验证：访问健康端点检查响应）
- [x] 场景 4：停止环境后重新启动 → MySQL、Redis、MinIO 数据仍存在（验证：重启后查询或读取既有数据）

## 安全

- [x] 实际 `.env` 文件不进入 Git（验证：`git status --ignored` 与 `git check-ignore`）
- [x] Git 跟踪文件中不存在 `.env`、密钥、证书或真实凭据（验证：`git ls-files` 与内容扫描）
- [x] Git 历史中不存在真实 `.env`、密钥或证书文件名（验证：`git log --all --name-only` 检查）
- [x] 示例环境变量均为明显假的占位值（验证：检查三份 `.env.example`）

## 验收记录（2026-09-17 16:54:25 CST）

- 健康检查返回：`{"status":{"api":"up","mysql":"up","redis":"up","minio":"up"},"ok":true}`。
- MySQL 验证返回：`InnoDB`、`utf8mb4`、`utf8mb4_0900_ai_ci`、UTC `+00:00`。
- Redis 验证返回：`appendonly yes`；清空 db 0 后 Celery 任务仍返回 `SUCCESS`。
- MinIO 四个必需桶均存在且为 `private`；预签名 PUT 返回 `200`，GET 内容为 `presigned-ok`。
- `ruff format --check` 返回 `21 files already formatted`；`ruff check` 返回 `All checks passed!`。
- 遗留安全问题：历史已跟踪 `backend/education_experiment_platform/db.sqlite3`；其中用户、会话和审计表均为空，仅包含 Django 初始化数据。
- 遗留安全问题：历史配置 `backend/education_experiment_platform/education_experiment_platform/settings.py` 硬编码 Django `SECRET_KEY`。需组长决定是否作废、轮换并重写历史。
- 2026-09-17 裁决：历史 `SECRET_KEY` 已作废，不重写历史；当前配置改为读取环境变量并在缺失时启动失败。
- 2026-09-17 裁决：`db.sqlite3` 不重写历史，改为普通删除提交并保持忽略。
