-- 先连接 postgres 默认库执行此文件（可选，需有 CREATEDB 权限）。
-- psql -U postgres -d postgres -f database/create_database.sql
-- 已有 travel_agent 数据库时不要重复执行。
CREATE DATABASE travel_agent ENCODING 'UTF8';
