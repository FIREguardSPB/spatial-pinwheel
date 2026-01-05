# Build Stage
FROM node:18-alpine as builder
WORKDIR /app

# Build arguments
ARG VITE_APP_VERSION=dev
ARG VITE_COMMIT_HASH=HEAD
ARG VITE_API_URL=/api/v1

# Set as environment variables for build
ENV VITE_APP_VERSION=$VITE_APP_VERSION
ENV VITE_COMMIT_HASH=$VITE_COMMIT_HASH
ENV VITE_API_URL=$VITE_API_URL

COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Serve Stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# Nginx config for SPA routing
RUN echo 'server { \
    listen 80; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://api:3000; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_set_header Host $host; \
        proxy_cache_bypass $http_upgrade; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
