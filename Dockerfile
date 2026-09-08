FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
FROM nginx:stable-alpine
ARG GRETA_RELEASE=unversioned
COPY --from=build /app/dist/client /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
RUN printf 'add_header X-Greta-Release "%s" always;\n' "$GRETA_RELEASE" > /etc/nginx/greta-release.conf
EXPOSE 80
