ARG NODE_BASE_IMAGE=node:24-alpine
ARG NGINX_BASE_IMAGE=nginx:1.29-alpine
FROM ${NODE_BASE_IMAGE} AS frontend
ARG APP_VERSION=0.1.0-p00
ARG OPENAPI_REVISION=v2-p00
ARG GIT_REVISION=development
ARG BUILD_TIME=development
ENV VITE_APP_VERSION=$APP_VERSION \
    VITE_OPENAPI_REVISION=$OPENAPI_REVISION \
    VITE_GIT_REVISION=$GIT_REVISION \
    VITE_BUILD_TIME=$BUILD_TIME
WORKDIR /workspace
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/apps ./apps
COPY frontend/packages ./packages
COPY frontend/tsconfig.json frontend/vite-env.d.ts ./
RUN npm ci --ignore-scripts && npm run build

FROM ${NGINX_BASE_IMAGE}
COPY infrastructure/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend /workspace/dist/user-web /srv/user-web
COPY --from=frontend /workspace/dist/teacher-web /srv/teacher-web
COPY --from=frontend /workspace/dist/admin-web /srv/admin-web
EXPOSE 8080
