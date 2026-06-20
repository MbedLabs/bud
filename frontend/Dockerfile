# Build stage
FROM node:20-alpine as build

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
RUN npm install

# Copy source files
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine

# Install envsubst (included in gettext)
RUN apk add --no-cache gettext

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config template
COPY nginx.conf /etc/nginx/conf.d/default.conf.template

# Create startup script
RUN echo '#!/bin/sh' > /docker-entrypoint.d/99-runtime-config.sh && \
    echo 'echo "window.runtimeConfig = {" > /usr/share/nginx/html/runtime-config.js' >> /docker-entrypoint.d/99-runtime-config.sh && \
    echo 'echo "  BLOOM_APP_URL: \"${BLOOM_APP_URL}\"," >> /usr/share/nginx/html/runtime-config.js' >> /docker-entrypoint.d/99-runtime-config.sh && \
    echo 'echo "  BUD_APP_URL: \"${BUD_APP_URL}\"" >> /usr/share/nginx/html/runtime-config.js' >> /docker-entrypoint.d/99-runtime-config.sh && \
    echo 'echo "};" >> /usr/share/nginx/html/runtime-config.js' >> /docker-entrypoint.d/99-runtime-config.sh && \
    echo 'envsubst "\$BACKEND_UPSTREAM" < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf' >> /docker-entrypoint.d/99-runtime-config.sh && \
    chmod +x /docker-entrypoint.d/99-runtime-config.sh

# Expose port
EXPOSE 80

# Default environment variables
ENV BACKEND_UPSTREAM=bud-backend.bud.svc.cluster.local:8000

CMD ["nginx", "-g", "daemon off;"]
