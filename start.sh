#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
# 数据库初始化参数：
#   1 = 创建缺失表，并在景点表为空时导入初始数据
#   0 = 跳过初始化，只连接并使用现有数据库
# 初始化操作不会删除表，也不会清空或覆盖已有数据。
INIT_DB="${1:-}"
if [ -z "$INIT_DB" ]; then
 read -r -p '是否初始化数据库？请输入 1（是）或 0（否）：' INIT_DB
fi
if [ "$INIT_DB" != '0' ] && [ "$INIT_DB" != '1' ]; then
 echo '错误：数据库初始化参数只能是 0 或 1。'
 echo '用法：./start.sh 1  或  ./start.sh 0'
 exit 2
fi
export TRIPMIND_INIT_DATABASE="$INIT_DB"
if [ ! -f .env ]; then
 echo '请 cp .env.example .env 并配置 PostgreSQL DATABASE_URL'
 exit 1
fi
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
