#!/usr/bin/env python3
"""
LLM Trading Analyzer - FastAPI 服务

说明：
- 全新服务化实现，不依赖旧的 pa/ 目录代码。
- 提供最小可用的 /health、/analyze（同步）、/backtest（异步）与 /jobs/{id} 端点。
- 数据来源：SQLite 数据库 data/forex_data.db。
"""

import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field, validator


# ============ 环境与全局配置 ============

try:
    # 尝试加载 .env.local / .env（可选）
    from dotenv import load_dotenv

    here = os.path.dirname(os.path.abspath(__file__))
    for env_name in (".env.local", ".env"):
        env_path = os.path.join(here, env_name)
        if os.path.exists(env_path):
            load_dotenv(env_path, override=False)
except Exception:
    pass

API_KEY_ENV = os.getenv("LLMTA_API_KEY", "")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "forex_data.db")


# ============ 安全鉴权 ============

def require_api_key(x_api_key: Optional[str] = Header(default=None)):
    """简单的 Header 鉴权。若未设置 LLMTA_API_KEY，则放行（便于本地调试）。"""
    if not API_KEY_ENV:
        return True
    if not x_api_key or x_api_key != API_KEY_ENV:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return True


# ============ 数据访问 ============

def _ensure_db_exists():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=500, detail=f"数据库不存在: {DB_PATH}")


def fetch_recent(symbol: str, timeframe: str, count: int) -> pd.DataFrame:
    import sqlite3

    _ensure_db_exists()
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT datetime, open, high, low, close, volume
            FROM price_data
            WHERE symbol = ? AND timeframe = ?
            ORDER BY datetime DESC
            LIMIT ?
            """,
            conn,
            params=(symbol, timeframe, count),
        )
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


def fetch_range(symbol: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
    import sqlite3

    _ensure_db_exists()
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            """
            SELECT datetime, open, high, low, close, volume
            FROM price_data
            WHERE symbol = ? AND timeframe = ?
              AND DATE(datetime) >= ? AND DATE(datetime) <= ?
            ORDER BY datetime ASC
            """,
            conn,
            params=(symbol, timeframe, start_date, end_date),
        )
    if df.empty:
        return df
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df


# ============ 基础分析（全新最小实现，不依赖 pa/） ============

class AnalyzeRequest(BaseModel):
    symbol: str = Field(default="EUR/USD")
    timeframe: str = Field(default="15min")
    count: int = Field(default=1000, ge=50, le=20000)
    rr: float = Field(default=2.0, ge=0.5, le=5.0, description="盈亏比R:R，例如2.0表示2R目标")


class TimeRange(BaseModel):
    start: Optional[datetime]
    end: Optional[datetime]


class Signal(BaseModel):
    index: int
    datetime: datetime
    is_bullish: bool
    label_text: str
    entry_price: float
    stop_loss_price: float
    risk_points: float
    result: str = Field(description="target/stop_loss/time_limit/pending")


class AnalyzeResponse(BaseModel):
    symbol: str
    timeframe: str
    count: int
    time_range: TimeRange
    stats: Dict[str, Any]
    trading_signals: List[Signal]
    version: str = "api-1.0"


def _generate_signals_and_results(df: pd.DataFrame, rr: float = 2.0, max_lookahead: int = 50) -> List[Dict[str, Any]]:
    """基于最小规则生成信号并评估结果：
    规则：
      - 看涨：当前收盘 > 前高
      - 看跌：当前收盘 < 前低
    风险：
      - 看涨止损 = min(当前低, 前低)
      - 看跌止损 = max(当前高, 前高)
    结果评估：
      - 向前最多检查 max_lookahead 根K线，先触及目标(±rr*risk)为止盈，先触及止损为止损，否则 time_limit 或 pending
    """
    signals: List[Dict[str, Any]] = []
    if len(df) < 2:
        return signals

    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        cur = df.iloc[i]

        is_bullish_signal = float(cur["close"]) > float(prev["high"]) and float(cur["close"]) > float(cur["open"])  # 收盘突破前高且阳线
        is_bearish_signal = float(cur["close"]) < float(prev["low"]) and float(cur["close"]) < float(cur["open"])  # 收盘跌破前低且阴线

        if not (is_bullish_signal or is_bearish_signal):
            continue

        if is_bullish_signal:
            entry = float(cur["close"]) 
            sl = min(float(cur["low"]), float(prev["low"]))
            risk = entry - sl
            label = "收盘>前高"
        else:
            entry = float(cur["close"]) 
            sl = max(float(cur["high"]), float(prev["high"]))
            risk = sl - entry
            label = "收盘<前低"

        # 跳过异常风险
        if risk <= 0:
            continue

        # 目标价
        if is_bullish_signal:
            target = entry + rr * risk
        else:
            target = entry - rr * risk

        # 向后检查结果
        result = "pending"
        for j in range(i + 1, min(i + 1 + max_lookahead, len(df))):
            bar = df.iloc[j]
            if is_bullish_signal:
                if float(bar["low"]) <= sl:
                    result = "stop_loss"
                    break
                if float(bar["high"]) >= target:
                    result = "target"
                    break
            else:
                if float(bar["high"]) >= sl:
                    result = "stop_loss"
                    break
                if float(bar["low"]) <= target:
                    result = "target"
                    break

        if result == "pending":
            # 如果有足够的bar检查，视为超时
            if i + 1 + max_lookahead <= len(df):
                result = "time_limit"

        signals.append(
            {
                "index": i + 1,  # 1-based
                "datetime": cur["datetime"],
                "is_bullish": is_bullish_signal,
                "label_text": label,
                "entry_price": entry,
                "stop_loss_price": sl,
                "risk_points": risk,
                "result": result,
            }
        )

    return signals


def analyze_symbol(symbol: str, timeframe: str, count: int, rr: float) -> AnalyzeResponse:
    df = fetch_recent(symbol, timeframe, count)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"无数据: {symbol} {timeframe}")

    signals = _generate_signals_and_results(df, rr=rr)
    wins = sum(1 for s in signals if s["result"] == "target")
    losses = sum(1 for s in signals if s["result"] == "stop_loss")
    completed = wins + losses
    winrate = (wins / completed * 100.0) if completed > 0 else 0.0

    resp = AnalyzeResponse(
        symbol=symbol,
        timeframe=timeframe,
        count=len(df),
        time_range=TimeRange(start=df["datetime"].min(), end=df["datetime"].max()),
        stats={
            "bullish": int((df["close"] > df["open"]).sum()),
            "bearish": int(len(df) - (df["close"] > df["open"]).sum()),
            "signals": len(signals),
            "wins": wins,
            "losses": losses,
            "winrate_estimate": round(winrate, 1),
            "rr": rr,
        },
        trading_signals=[Signal(**s) for s in signals],
    )
    return resp


# ============ 异步回测（最小实现） ============

class BacktestParams(BaseModel):
    rr: float = Field(default=2.0, ge=0.5, le=5.0)


class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    params: BacktestParams = Field(default_factory=BacktestParams)

    @validator("start_date", "end_date")
    def _validate_date(cls, v: str) -> str:
        # 允许 YYYY-MM-DD
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except Exception:
            raise ValueError("日期格式需为 YYYY-MM-DD")
        return v


class BacktestMetrics(BaseModel):
    winrate: float
    wins: int
    losses: int
    time_limit: int
    pending: int
    signals: int
    rr: float
    avg_r: float
    profit_factor: float


class BacktestResult(BaseModel):
    symbol: str
    timeframe: str
    period: Dict[str, str]
    params: Dict[str, Any]
    metrics: BacktestMetrics


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[BacktestResult] = None
    error: Optional[str] = None


_JOBS: Dict[str, Dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()


def _run_backtest_job(job_id: str, req: BacktestRequest):
    try:
        df = fetch_range(req.symbol, req.timeframe, req.start_date, req.end_date)
        if df.empty:
            raise RuntimeError("指定时间段无数据")

        signals = _generate_signals_and_results(df, rr=req.params.rr)
        wins = sum(1 for s in signals if s["result"] == "target")
        losses = sum(1 for s in signals if s["result"] == "stop_loss")
        tl = sum(1 for s in signals if s["result"] == "time_limit")
        pending = sum(1 for s in signals if s["result"] == "pending")
        completed = wins + losses
        winrate = (wins / completed * 100.0) if completed > 0 else 0.0

        # 用 R 计量的简化盈亏：胜=+rr，负=-1，忽略time_limit/pending
        total_r = wins * req.params.rr - losses * 1.0
        avg_r = (total_r / completed) if completed > 0 else 0.0
        gross_profit = wins * req.params.rr
        gross_loss = losses * 1.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        result = BacktestResult(
            symbol=req.symbol,
            timeframe=req.timeframe,
            period={"from": req.start_date, "to": req.end_date},
            params={"rr": req.params.rr},
            metrics=BacktestMetrics(
                winrate=round(winrate, 2),
                wins=wins,
                losses=losses,
                time_limit=tl,
                pending=pending,
                signals=len(signals),
                rr=req.params.rr,
                avg_r=round(avg_r, 3),
                profit_factor=round(profit_factor, 3),
            ),
        )

        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "succeeded"
            _JOBS[job_id]["result"] = result
    except Exception as e:
        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "failed"
            _JOBS[job_id]["error"] = str(e)


# ============ FastAPI 实例与路由 ============

app = FastAPI(title="LLM Trading Analyzer API", version="1.0")


@app.get("/health")
def health(_: bool = Depends(require_api_key)):
    return {"status": "ok", "db": os.path.exists(DB_PATH)}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, _: bool = Depends(require_api_key)):
    return analyze_symbol(req.symbol, req.timeframe, req.count, rr=req.rr)


@app.post("/backtest", response_model=JobStatusResponse)
def backtest(req: BacktestRequest, _: bool = Depends(require_api_key)):
    job_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "running", "created_at": time.time()}

    t = threading.Thread(target=_run_backtest_job, args=(job_id, req), daemon=True)
    t.start()

    return JobStatusResponse(job_id=job_id, status="pending")


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str, _: bool = Depends(require_api_key)):
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")

        status = job.get("status", "pending")
        result = job.get("result")
        error = job.get("error")

    return JobStatusResponse(job_id=job_id, status=status, result=result, error=error)


# ============ 下载任务：最近一年分段下载（使用 TwelveDataClient） ============
class DownloadRequest(BaseModel):
    symbol: str = Field(default="EUR/USD")
    timeframe: str = Field(default="1min")
    chunk_days: float = Field(default=3.5, ge=0.1, le=30.0)


class DownloadResult(BaseModel):
    symbol: str
    timeframe: str
    batches: int
    total_rows: int


def _run_download_job(job_id: str, req: DownloadRequest):
    try:
        # 延迟导入，避免服务启动即引入requests等重量依赖
        from twelve_data_client import TwelveDataClient

        client = TwelveDataClient()  # 从环境变量或 .env.local 读取 API Key
        stats = client.download_last_year_in_chunks(
            symbol=req.symbol, timeframe=req.timeframe, chunk_days=req.chunk_days
        )
        result = DownloadResult(
            symbol=req.symbol,
            timeframe=req.timeframe,
            batches=int(stats.get("batches", 0)),
            total_rows=int(stats.get("total_rows", 0)),
        )
        with _JOBS_LOCK:
            _JOBS[job_id] = {"status": "succeeded", "result": result}
    except Exception as e:
        with _JOBS_LOCK:
            _JOBS[job_id] = {"status": "failed", "error": str(e)}


@app.post("/download", response_model=JobStatusResponse)
def download_last_year(req: DownloadRequest, _: bool = Depends(require_api_key)):
    job_id = f"dl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "running", "created_at": time.time()}
    t = threading.Thread(target=_run_download_job, args=(job_id, req), daemon=True)
    t.start()
    return JobStatusResponse(job_id=job_id, status="pending")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fastapi_app:app", host="0.0.0.0", port=8000, reload=True)
