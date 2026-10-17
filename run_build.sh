#!/bin/bash
# 统一构建入口：任意 cwd 均可执行（内部自切换到 client_app）
cd "$(dirname "$0")/client_app" || exit 1
cmd //c build.bat < /dev/null
