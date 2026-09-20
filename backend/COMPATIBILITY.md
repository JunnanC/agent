# 技术基线事实源

- 生成日期：2026-09-20
- 依据：`架构设计_v2/00_架构总纲.md:86-92`、`学生端开发任务书.md:111`
- Python：3.13
- Django：5.2.17
- Django REST Framework：3.18.1
- drf-spectacular：0.30.0
- Celery：5.6
- django-celery-beat：2.9
- MySQL：8.0
- Redis：7
- OpenAPI：3.0.3

## 依赖锁定状态

`PENDING: requirements.txt 未形成全量锁定`。仓库既有 `requirements.txt` 包含开放式区间约束；按 B1 “既有依赖清单只追加缺失项并保留既有版本约束”的要求，本切片未改写既有约束。

## OPEN-DB-07

Django `BigAutoField` 在 MySQL 上生成 signed `BIGINT`，而 `架构设计_v2/07:15` 规定主键为 `BIGINT UNSIGNED`，外键引用列可能触发 MySQL errno 3780。按 B1 执行 `django.db.models.BigAutoField`；该 signed/unsigned 差异留待 V00 决策闸门裁决，不自行修改 DDL 或字段类型。

## 后续模型约定

后续所有 Django model 必须显式设置 `class Meta: db_table = "<DDL 表名>"`，不得依赖 Django 默认表名推断。

## 运行纪律

本地验证必须使用 ASGI 容器，例如：

```powershell
uvicorn education_experiment_platform.asgi:application --host 127.0.0.1 --port 8000
```

不得使用 WSGI 同步容器验证后续 SSE 能力。
