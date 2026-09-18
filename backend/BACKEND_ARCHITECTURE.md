# 后端架构约定

## 基本结构

后端采用 Django 官方教程式结构：主项目包与各业务 app 平级，一个 app 一个文件夹。

```text
backend/
└── education_experiment_platform/
    ├── celery.py        # 独立 Celery Worker 入口
    ├── manage.py
    ├── main/            # 主项目配置包，只负责 Django 配置与装配
    └── runtime/         # 当前唯一实际业务 app
```

## 架构规则

1. **主项目包与 app 平级**
   - `main/` 是主项目配置包；
   - 每个 Django app 直接放在项目根目录下；
   - 不使用 `apps/` 聚合目录，不把多个 app 嵌套在同一文件夹下。

2. **一个 app 一个文件夹**
   - 一个 app 对应一个明确业务能力；
   - 后续新增 app 时，直接在项目根目录创建新的平级文件夹；
   - 禁止为了占位而批量创建空 app，只有在实际开始开发该业务能力时才新增。

3. **主项目包只做配置与装配**
   - `main/` 只保留 `settings.py`、`urls.py`、`asgi.py`、`wsgi.py`；
   - 业务逻辑、模型、服务、仓储不得写入 `main/`。

4. **Celery 独立于主项目包**
   - Celery 入口固定为项目根目录下的 `celery.py`；
   - Worker 启动方式：`celery -A celery worker`；
   - 各业务 app 的任务放在各自 app 的 `tasks.py` 中，由 Celery 自动发现；
   - Celery 不是业务 app，不放入业务 app 文件夹。

5. **App 内部结构按需生长**
   - app 当前可以只有实际使用的文件；
   - 进入业务开发后按需补充：

   ```text
   runtime/
   ├── __init__.py
   ├── apps.py
   ├── models.py
   ├── services.py
   ├── selectors.py
   ├── serializers.py
   ├── views.py
   ├── urls.py
   ├── tasks.py
   ├── migrations/
   └── tests/
   ```

   - 不提前创建空的 `models.py`、`views.py`、`serializers.py` 或 migration。

6. **当前保留的 app**
   - `runtime/`：当前唯一有实际代码的 app；
   - 其他业务域 app 待实际开发时再创建。

## 开发约束

- 新增 app 前先确认其业务边界，避免多个业务域塞进一个 app。
- 跨 app 调用必须通过明确的 service/API 层，不允许直接依赖另一个 app 的内部函数。
- `main/` 不承载业务逻辑。
- Celery 任务放在所属 app 的 `tasks.py`，不在 `main/` 中堆任务。
