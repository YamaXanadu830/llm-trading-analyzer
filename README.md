# LLM交易分析系统（服务化 + n8n）

本项目已重构为“服务化 API + n8n 流程编排”的形态：

- Python 侧提供 FastAPI 服务，读取本地 SQLite（`data/forex_data.db`），输出结构化 JSON；
- n8n 通过 HTTP 节点调用 `/analyze`（同步）与 `/backtest`（异步），并结合 LLM 进行解读、推送与归档；
- 旧版 `pa/` 与交互式 CLI 已移除，不再依赖。

## 🚀 快速开始

### 安装依赖
```bash
cd llm-trading-analyzer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 配置环境变量
```bash
cp .env.example .env.local
# Twelve Data API（下载行情数据）：
#   TWELVEDATA_API_KEY=xxxx
# FastAPI 鉴权（可选）：
#   LLMTA_API_KEY=your_api_key
```

### 启动 FastAPI 服务
```bash
uvicorn fastapi_app:app --host 0.0.0.0 --port 8000 --reload
```

## 📊 数据管理（TwelveData API）
```bash
# 更新15分钟数据
python3 twelve_data_client.py --timeframe 15min --size 1000

# 日期范围下载（推荐）
python3 twelve_data_client.py --timeframe 4h --start-date 2020-01-01 --end-date 2024-12-31

# 年份下载
python3 twelve_data_client.py --timeframe 4h --year 2023

# 从2020年开始下载到现在
python3 twelve_data_client.py --timeframe 4h --from-2020

# 多时间周期下载
python3 twelve_data_client.py --timeframes 15min,1h,4h,1day --size 1000

# 查看数据库统计
python3 twelve_data_client.py --show-stats

# 最近一年 1min 分段下载（约5000根/批）
python3 twelve_data_client.py --timeframe 1min --last-year-chunked --chunk-days 3.5
```

注意：Twelve Data 免费额度当前为 8 次/分钟、800 次/天（以官方为准），代码内已内置频控与批处理节流策略。

## 🌐 FastAPI 服务（n8n 接入）

- `GET /health`：健康检查（需数据库存在）
- `POST /analyze`：同步分析最近 K 线（最小规则：收盘突破前高/前低 + RR 目标）
  - 示例：`{"symbol":"EUR/USD","timeframe":"15min","count":1000,"rr":2.0}`
  - 返回：`stats`、`time_range`、`trading_signals` 等结构化 JSON
- `POST /backtest`：异步回测（返回 `job_id`）
- `GET /jobs/{id}`：轮询作业状态/结果

### 示例请求
```bash
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"EUR/USD","timeframe":"15min","count":1000,"rr":2.0}' | jq '.'
```

### n8n 接入要点
- HTTP Request → `/analyze`（同步播报）
- HTTP Request → `/backtest` → Wait → `/jobs/{id}`（异步回测）
- Header 鉴权（可选）：在 `.env.local` 配置 `LLMTA_API_KEY`，n8n 节点 Header 加 `X-API-Key`

## 📁 项目结构（精简版）

```
llm-trading-analyzer/
├── fastapi_app.py          # FastAPI 服务入口（核心）
├── twelve_data_client.py   # TwelveData 数据下载与入库
├── data/
│   └── forex_data.db       # SQLite 数据库（运行后生成/填充）
├── requirements.txt
└── .env.example            # 示例环境变量（含 LLMTA_API_KEY）
```

## 📝 更新日志

### v3.0.0 (2025-09)
- ✨ 服务化重构：新增 FastAPI（/analyze、/backtest、/jobs）
- 🔁 n8n 编排：HTTP 调用 + LLM 解读 + 推送
- 🗑️ 移除旧版 `pa/` 与 CLI 脚本（main/参数分析/测试）

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 与 PR！
