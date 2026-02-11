.PHONY: up down logs restart clean build

# 启动所有服务
up:
	docker-compose up -d

# 停止所有服务
down:
	docker-compose down

# 查看日志
logs:
	docker-compose logs -f

# 重启服务
restart:
	docker-compose restart

# 清理（包括数据卷）
clean:
	docker-compose down -v
	docker system prune -f

# 重新构建并启动
build:
	docker-compose up -d --build

# 查看服务状态
status:
	docker-compose ps
