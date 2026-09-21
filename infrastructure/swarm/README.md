# P00 Swarm staging baseline

The stack runs stateless platform services only. MySQL, Redis, MongoDB Replica Set, and MinIO must be supplied through an external managed service or a separately reviewed replicated data stack with non-local persistent storage. The P00 stack deliberately does not claim HA for a single-node volume.

Required node labels are boolean labels under `edu.role`: `edge`, `app`, `worker`, `runtime`, and `data`. A node may carry more than one label in a small staging cluster, but data and student runtime workloads should not be co-located without an explicit review. Configure each node's Docker daemon to permit the Fluentd logging driver; the global Fluent Bit service listens on host port 24224 and buffers locally when the MongoDB sink is unavailable.

Build the staging edge image with `infrastructure/nginx/Dockerfile.prod`; it redirects port 80 to TLS and reads the certificate from Swarm secrets. Create versioned configs and secrets before deploying. Never pass secret values through Swarm configs or the command line history. Required environment variables are `REGISTRY`, `IMAGE_TAG`, `MYSQL_HOST`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `MINIO_ENDPOINT`, and `CLAMAV_HOST`. Required secrets are `django_secret_key`, `mysql_app_password`, `mongodb_uri`, `tls_certificate`, and `tls_private_key`.

```powershell
./scripts/bootstrap-swarm.ps1 -ManagerNodes manager-1,manager-2,manager-3
docker stack deploy --with-registry-auth -c infrastructure/swarm/stack.yml edu-platform
```

The three-manager quorum, external storage failover, rolling rollback, and node-loss exercises must be recorded in a staging environment. They cannot be certified by a single-node Docker Desktop run.
