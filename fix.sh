#!/bin/bash
cat << 'EOF' > /etc/nginx/conf.d/promo.conf
server {
    listen 80;
    server_name ppsai.chat;

    location / {
        root /var/www/html/promo;
        index index.html;
    }

    location /safecleaner {
        alias /var/www/html/safecleaner;
        index index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF
nginx -t && nginx -s reload
