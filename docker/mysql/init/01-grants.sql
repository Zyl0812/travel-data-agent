-- 让 zyl 用户可以从任意主机连接，并具备建库/删库等全权限
-- init_db.py 中会执行 DROP DATABASE / CREATE DATABASE，必须授权
CREATE USER IF NOT EXISTS 'zyl'@'%' IDENTIFIED BY '123456';
GRANT ALL PRIVILEGES ON *.* TO 'zyl'@'%' WITH GRANT OPTION;

-- 预创建语义元数据库（业务库 travel 由 travel-data/init_db.py 自动建）
CREATE DATABASE IF NOT EXISTS meta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

FLUSH PRIVILEGES;
