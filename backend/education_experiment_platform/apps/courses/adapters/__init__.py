"""端口实现（doc 02 §一 ``adapters/``）。

courses 域目前**不需要** adapter：它不调用任何外部系统，而 doc 06 §二 明令
禁止把 Docker/MinIO/模型调用放进数据库事务。actor 与教师资格由 ``ports.py``
注入，其实现归 accounts（P02）所有。

保留这个包是为了让 doc 02 §一 规定的目录布局稳定：P03-B 的批量名册导入、
课程复制 job 若需要对象存储或队列适配器，落在这里而不是塞进 service。
"""
