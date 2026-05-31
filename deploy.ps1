Write-Host "Deploying Backend to VPS..."
ssh root@65.49.220.245 "mkdir -p /opt/safecleaner_backend"
scp -r "D:\Coding\app\SafeCleanerPro\web_backend\*" root@65.49.220.245:/opt/safecleaner_backend/
ssh root@65.49.220.245 "cd /opt/safecleaner_backend && docker compose up -d --build"

Write-Host "Deploying Frontend to VPS..."
ssh root@65.49.220.245 "mkdir -p /var/www/html/safecleaner"
scp -r "D:\Coding\app\SafeCleanerPro\web_frontend\*" root@65.49.220.245:/var/www/html/safecleaner/

Write-Host "Injecting Nginx Rules..."
ssh root@65.49.220.245 "if ! grep -q 'location /safecleaner' /etc/nginx/conf.d/promo.conf; then sed -i '/location \/ {/i \    location \/safecleaner {\n        alias \/var\/www\/html\/safecleaner;\n        index index.html;\n    }' /etc/nginx/conf.d/promo.conf; fi"
ssh root@65.49.220.245 "if ! grep -q 'location /api' /etc/nginx/conf.d/promo.conf; then sed -i '/location \/ {/i \    location \/api {\n        proxy_pass http:\/\/127.0.0.1:5000;\n        proxy_set_header Host \$host;\n        proxy_set_header X-Real-IP \$remote_addr;\n    }' /etc/nginx/conf.d/promo.conf; fi"

Write-Host "Reloading Nginx..."
ssh root@65.49.220.245 "nginx -t && nginx -s reload"

Write-Host "Deployment Complete!"
