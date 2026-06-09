# 美股财报异动预警系统

一个面向 MVP 的自动化扫描系统，用于抓取未来 7-14 天即将发布财报的美股公司，并结合价格表现、新闻情绪、分析师变化生成关注名单。当前默认扫描未来 7 天，并过滤部分小市值股票，以减少刷新耗时。

## 已实现能力

- 获取未来若干天财报日历（使用 Nasdaq 公开接口）
- 计算近 7 天、近 30 天价格表现与相对 SPY 强弱
- 抓取最近 30 天新闻并调用 LLM 或关键词 fallback 做结构化分析
- 获取分析师目标价与升级/降级变化
- 基于规则生成 0-100 综合评分与高/中/低优先级
- 使用 SQLite 保存历史扫描数据
- 使用 Streamlit 展示 watchlist，并支持 CSV 导出

## 项目结构

```text
earnings-alert-system/
├── app.py
├── main.py
├── requirements.txt
├── .env.example
├── README.md
├── config.py
├── data/
│   └── app.db
├── src/
│   ├── __init__.py
│   ├── analyst_data.py
│   ├── database.py
│   ├── earnings_calendar.py
│   ├── llm_analyzer.py
│   ├── models.py
│   ├── news_collector.py
│   ├── price_analysis.py
│   ├── scoring.py
│   ├── utils.py
│   └── watchlist.py
└── tests/
    └── test_scoring.py
```

## 环境准备

1. 创建虚拟环境并安装依赖：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. 复制环境变量模板：

```bash
copy .env.example .env
```

3. 可选环境变量：

```text
OPENAI_API_KEY=你的_key
DATABASE_URL=sqlite:///data/app.db
SCAN_WINDOW_DAYS=7
MAX_SCAN_SYMBOLS=50
MIN_MARKET_CAP_USD=1000000000
```

说明：

- 不配置任何 API Key 也可以启动并运行基础扫描。
- 缺少 `OPENAI_API_KEY` 时，新闻分析会自动切换到关键词 fallback。
- 财报日历默认走 Nasdaq 公开接口，不需要单独配置 API Key。
- `FINNHUB_API_KEY` 现在是可选项，主要用于新闻和分析师模块的补充数据。
- 缺少分析师相关可用数据时，系统不会崩溃，只会降低结果完整度。
- `MAX_SCAN_SYMBOLS` 和 `MIN_MARKET_CAP_USD` 可用于限制扫描数量、过滤小票，缩短刷新时间。

## 运行方式

执行一次扫描：

```bash
python main.py --days 7
```

启动前端：

```bash
streamlit run app.py
```

运行测试：

```bash
pytest
```

## 模块说明

- `src/earnings_calendar.py`：拉取未来财报事件
- `src/price_analysis.py`：计算价格和成交量指标
- `src/news_collector.py`：抓取最近新闻
- `src/llm_analyzer.py`：新闻结构化分析与 fallback
- `src/analyst_data.py`：分析师目标价与升级/降级数据
- `src/scoring.py`：集中维护评分逻辑
- `src/watchlist.py`：串联主流程并持久化结果
- `data/app.log`：运行日志，包含 yfinance 和扫描过滤的告警信息

## 后续扩展建议

- 增加 Reddit / 做空 / 期权模块
- 引入更多可替代的数据源
- 保存财报后收益，构建机器学习训练集
- 增加回测报表与历史对比页面
