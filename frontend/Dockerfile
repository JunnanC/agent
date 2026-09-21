ARG NODE_BASE_IMAGE=node:24-alpine
FROM ${NODE_BASE_IMAGE} AS build

ARG APP_VERSION=0.1.0-p00
ARG OPENAPI_REVISION=v2-p00
ARG GIT_REVISION=development
ARG BUILD_TIME=development
ENV VITE_APP_VERSION=$APP_VERSION \
    VITE_OPENAPI_REVISION=$OPENAPI_REVISION \
    VITE_GIT_REVISION=$GIT_REVISION \
    VITE_BUILD_TIME=$BUILD_TIME

WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps ./apps
COPY packages ./packages
COPY tsconfig.json vite-env.d.ts ./
RUN npm ci --ignore-scripts && npm run build

FROM scratch AS artifacts
COPY --from=build /workspace/dist /
