FROM python:3.11-slim

WORKDIR /app

# 装依赖（先拷 requirements，利用 Docker 缓存层）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 拷代码和配置
COPY backend/ ./backend/
COPY config/ ./config/

# 数据目录（docker-compose 会挂 volume 持久化）
RUN mkdir -p /app/data

ENV DB_PATH=/app/data/app.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
