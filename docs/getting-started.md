# 快速入门

## 1. 环境

- Python 3.10+, Node.js 18+, Docker Desktop

## 2. 安装

```bash
git clone https://github.com/studyyyyyyyy-cn/RAG.git && cd RAG
cd backend && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
cd ../frontend && npm install
```

## 3. 启动

双击 `start.bat` 或：

```bash
docker-compose up -d neo4j
cd backend && venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
cd frontend && npx vite --host 0.0.0.0
```

## 4. 配置

1. 系统设置 → 添加 LLM
2. 知识库 → 创建 KB → 上传文档 → 分块
3. 向量状态 → 重载确认入库
4. 知识图谱 → 重建图谱
5. 智能问答 → 提问

## 5. 访问

| 页面 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API | http://localhost:8000/docs |
| 图谱 | http://localhost:5173/knowledge-graph |
| 向量 | http://localhost:5173/vector-status |
