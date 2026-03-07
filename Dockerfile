FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_APP_VERSION=dev
ARG VITE_COMMIT_HASH=HEAD
ARG VITE_API_URL=/api/v1

ENV VITE_APP_VERSION=$VITE_APP_VERSION \
    VITE_COMMIT_HASH=$VITE_COMMIT_HASH \
    VITE_API_URL=$VITE_API_URL

COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:stable-alpine
RUN apk add --no-cache wget
COPY --from=build /app/dist /usr/share/nginx/html
RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://api:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD wget -qO- http://localhost/ >/dev/null || exit 1
CMD ["nginx", "-g", "daemon off;"]
