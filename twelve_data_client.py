#!/usr/bin/env python3
"""
Twelve Data API客户端 - EURUSD外汇数据获取
免费版限制: 8次/分钟, 800次/天 - 完全满足需求
"""

import requests
import pandas as pd
import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import os

def validate_date_format(date_string: str) -> bool:
    """验证日期格式 yyyy-MM-dd"""
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

class TwelveDataClient:
    """Twelve Data API客户端"""
    
    BASE_URL = "https://api.twelvedata.com"
    
    def __init__(self, api_key: str = None):
        """
        初始化客户端
        
        Args:
            api_key: API密钥（优先于环境变量）。如未提供，将从环境变量读取。
        """
        self.session = requests.Session()
        
        # 优先使用显式传入的 api_key；否则尝试从环境变量/.env.local 加载
        self.api_key = api_key or self._load_api_key_from_env()
        
        # 免费版限制管理
        self.calls_per_minute = 8
        self.calls_per_day = 800
        self.call_times = []
        
        # 初始化数据库
        self.init_database()
    
    def init_database(self):
        """初始化SQLite数据库（路径锚定到模块目录 data/）"""
        # 将数据目录固定为当前模块同级的 data/
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, "forex_data.db")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    datetime TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timeframe, datetime)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_symbol_timeframe_datetime 
                ON price_data(symbol, timeframe, datetime)
            """)
    
    def _check_rate_limit(self):
        """检查API调用频率限制"""
        now = datetime.now()
        
        # 清理1分钟前的调用记录
        self.call_times = [t for t in self.call_times if (now - t).seconds < 60]
        
        # 检查是否超过每分钟限制
        if len(self.call_times) >= self.calls_per_minute:
            wait_time = 60 - (now - self.call_times[0]).seconds
            print(f"⏳ API调用频率限制，等待 {wait_time} 秒...")
            time.sleep(wait_time + 1)
            self.call_times = []
    
    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """发起API请求"""
        self._check_rate_limit()
        
        if not self.api_key:
            raise RuntimeError("未配置 TwelveData API Key。请设置环境变量 'TWELVEDATA_API_KEY' 或在项目目录创建 .env.local 并配置 TWELVEDATA_API_KEY=")
        
        params['apikey'] = self.api_key
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            self.call_times.append(datetime.now())
            
            data = response.json()
            
            # 检查API错误
            if 'status' in data and data['status'] == 'error':
                raise Exception(f"API错误: {data.get('message', '未知错误')}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ API请求失败: {e}")
            raise

    def _load_api_key_from_env(self) -> Optional[str]:
        """从环境变量或 .env.local 读取 API Key（不报错，延迟到请求阶段校验）。"""
        import os
        api_key = os.getenv("TWELVEDATA_API_KEY") or os.getenv("TWELVE_DATA_API_KEY")
        if api_key:
            return api_key
        
        # 尝试加载项目内 .env.local / .env（若安装了 python-dotenv）
        try:
            from dotenv import load_dotenv
            project_root = os.path.dirname(os.path.abspath(__file__))
            # 优先 .env.local，然后 .env
            for env_name in [".env.local", ".env"]:
                env_path = os.path.join(os.path.dirname(project_root), env_name)
                if os.path.exists(env_path):
                    load_dotenv(env_path, override=False)
                    api_key = os.getenv("TWELVEDATA_API_KEY") or os.getenv("TWELVE_DATA_API_KEY")
                    if api_key:
                        return api_key
        except Exception:
            # 不强依赖 python-dotenv，找不到就忽略，交由请求阶段提示
            pass
        
        return None
    
    def get_forex_data(self, 
                      symbol: str = "EUR/USD", 
                      interval: str = "15min", 
                      outputsize: int = 2000,
                      start_date: str = None,
                      end_date: str = None) -> pd.DataFrame:
        """
        获取外汇K线数据
        
        Args:
            symbol: 货币对，默认EUR/USD
            interval: 时间周期 (1min, 5min, 15min, 30min, 45min, 1h, 2h, 4h, 1day, 1week, 1month)
            outputsize: 数据数量，默认2000根K线
            start_date: 开始日期 (格式: YYYY-MM-DD)
            end_date: 结束日期 (格式: YYYY-MM-DD)
        
        Returns:
            pandas.DataFrame: K线数据
        """
        if start_date and end_date:
            print(f"📊 获取 {symbol} {interval} 数据，日期范围: {start_date} ~ {end_date}")
        else:
            print(f"📊 获取 {symbol} {interval} 数据，数量: {outputsize}")
        
        params = {
            'symbol': symbol,
            'interval': interval,
            'format': 'json'
        }
        
        # 根据是否指定日期范围选择参数
        if start_date and end_date:
            params['start_date'] = start_date
            params['end_date'] = end_date
        else:
            params['outputsize'] = outputsize
        
        try:
            data = self._make_request('time_series', params)
            
            if 'values' not in data:
                print(f"❌ 数据格式错误: {data}")
                return pd.DataFrame()
            
            # 转换为DataFrame
            df = pd.DataFrame(data['values'])
            
            if df.empty:
                print("❌ 获取到空数据")
                return df
            
            # 数据类型转换
            df['datetime'] = pd.to_datetime(df['datetime'])
            for col in ['open', 'high', 'low', 'close']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            if 'volume' in df.columns:
                df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
            else:
                df['volume'] = 0
            
            # 按时间排序
            df = df.sort_values('datetime').reset_index(drop=True)
            
            print(f"✅ 成功获取 {len(df)} 根K线数据")
            return df
            
        except Exception as e:
            print(f"❌ 数据获取失败: {e}")
            return pd.DataFrame()
    
    def save_to_database(self, df: pd.DataFrame, symbol: str, timeframe: str):
        """保存数据到SQLite数据库"""
        if df.empty:
            print("❌ 无数据可保存")
            return
        
        print(f"💾 保存数据到数据库: {symbol} {timeframe}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                for _, row in df.iterrows():
                    conn.execute("""
                        INSERT OR REPLACE INTO price_data 
                        (symbol, timeframe, datetime, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol, timeframe, 
                        row['datetime'].strftime('%Y-%m-%d %H:%M:%S'),
                        row['open'], row['high'], row['low'], row['close'],
                        row['volume'] if pd.notna(row['volume']) else 0
                    ))
                
                print(f"✅ 已保存 {len(df)} 条记录")
                
        except Exception as e:
            print(f"❌ 数据库保存失败: {e}")
    
    def load_from_database(self, symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
        """从数据库加载数据"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT datetime, open, high, low, close, volume
                    FROM price_data 
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY datetime DESC
                    LIMIT ?
                """
                df = pd.read_sql_query(query, conn, params=(symbol, timeframe, limit))
                
                if not df.empty:
                    df['datetime'] = pd.to_datetime(df['datetime'])
                    df = df.sort_values('datetime').reset_index(drop=True)
                    print(f"📂 从数据库加载 {len(df)} 条记录")
                
                return df
                
        except Exception as e:
            print(f"❌ 数据库加载失败: {e}")
            return pd.DataFrame()
    
    def get_eurusd_data(self, use_cache: bool = True) -> pd.DataFrame:
        """
        获取EURUSD 15分钟数据 (优化版)
        
        Args:
            use_cache: 是否使用数据库缓存
        
        Returns:
            pandas.DataFrame: EURUSD K线数据
        """
        symbol = "EUR/USD"
        timeframe = "15min"
        
        # 尝试从缓存加载
        if use_cache:
            cached_data = self.load_from_database(symbol, timeframe)
            if not cached_data.empty:
                # 检查最新数据时间
                latest_time = cached_data['datetime'].max()
                time_diff = datetime.now() - latest_time.replace(tzinfo=None)
                
                # 如果数据较新(< 1小时)，直接使用缓存
                if time_diff < timedelta(hours=1):
                    print(f"✅ 使用缓存数据，最新时间: {latest_time}")
                    return cached_data
        
        # 从API获取新数据
        df = self.get_forex_data(symbol, timeframe, 200)
        
        if not df.empty:
            self.save_to_database(df, symbol, timeframe)
        
        return df
    
    def get_multi_timeframe_data(self, 
                                symbol: str = "EUR/USD", 
                                timeframes: List[str] = None,
                                outputsize: int = 200,
                                use_cache: bool = True) -> Dict[str, pd.DataFrame]:
        """
        批量获取多个时间周期的K线数据
        
        Args:
            symbol: 货币对
            timeframes: 时间周期列表，默认["15min", "1h", "4h", "1day"]
            outputsize: 每个时间周期的数据量
            use_cache: 是否使用缓存
        
        Returns:
            Dict[str, pd.DataFrame]: 时间周期->数据的字典
        """
        if timeframes is None:
            timeframes = ["15min", "1h", "4h", "1day"]
        
        print(f"📊 批量获取 {symbol} 多时间周期数据: {timeframes}")
        result = {}
        
        for timeframe in timeframes:
            try:
                # 优先使用缓存
                if use_cache:
                    cached_data = self.load_from_database(symbol, timeframe)
                    if not cached_data.empty:
                        latest_time = cached_data['datetime'].max()
                        time_diff = datetime.now() - latest_time.replace(tzinfo=None)
                        
                        # 根据时间周期调整缓存有效期
                        cache_hours = {"15min": 1, "1h": 2, "4h": 8, "1day": 24}.get(timeframe, 2)
                        if time_diff < timedelta(hours=cache_hours):
                            print(f"✅ {timeframe} 使用缓存数据")
                            result[timeframe] = cached_data
                            continue
                
                # 从API获取新数据
                df = self.get_forex_data(symbol, timeframe, outputsize)
                if not df.empty:
                    self.save_to_database(df, symbol, timeframe)
                    result[timeframe] = df
                else:
                    print(f"⚠️ {timeframe} 获取数据失败")
                    
            except Exception as e:
                print(f"❌ {timeframe} 处理失败: {e}")
        
        print(f"✅ 成功获取 {len(result)} 个时间周期的数据")
        return result

    def download_last_year_in_chunks(self,
                                     symbol: str = "EUR/USD",
                                     timeframe: str = "1min",
                                     chunk_days: float = 3.5) -> Dict[str, Any]:
        """
        下载最近一年的数据（默认1min），按窗口分段入库，窗口跨度约等于5000根/次。

        说明：
        - 1min 周期约 1 天 ≈ 1440 根，5000 根≈ 3.47 天；默认 chunk_days=3.5 贴近 5000 根/批。
        - 使用日期窗口（YYYY-MM-DD）进行分段，TwelveData 将返回区间内所有可用数据。
        - 存在重复数据时由数据库 UNIQUE(symbol,timeframe,datetime) 去重。
        """
        print("\n🚀 分段下载最近一年的数据")
        print(f"🕒 周期: {timeframe}, 窗口: {chunk_days} 天/次, 品种: {symbol}")

        end_dt = datetime.now().date()
        start_dt = (datetime.now() - timedelta(days=365)).date()

        cursor = start_dt
        total_inserted = 0
        batch = 0

        while cursor < end_dt:
            batch += 1
            window_start = cursor
            window_end = min(end_dt, cursor + timedelta(days=chunk_days))

            sd = window_start.strftime('%Y-%m-%d')
            ed = window_end.strftime('%Y-%m-%d')

            print(f"\n[{batch}] 📥 下载区间: {sd} ~ {ed}")
            df = self.get_forex_data(symbol, timeframe, start_date=sd, end_date=ed)
            if not df.empty:
                before = len(df)
                self.save_to_database(df, symbol, timeframe)
                total_inserted += before
                print(f"   ✅ 本批数据: {before} 条，累计: {total_inserted}")
            else:
                print("   ⚠️ 本批无数据（可能为周末/节假日/数据缺失）")

            # 移动窗口
            cursor = window_end

        print("\n🎉 分段下载完成!")
        print(f"📊 累计处理记录（含去重前计数）: {total_inserted:,}")
        return {"batches": batch, "total_rows": total_inserted}
    
    def get_data_by_timeframe(self, 
                             symbol: str, 
                             timeframe: str, 
                             limit: int = 200) -> pd.DataFrame:
        """
        按时间周期查询已存储的数据
        
        Args:
            symbol: 交易品种
            timeframe: 时间周期
            limit: 数据条数限制
        
        Returns:
            pandas.DataFrame: K线数据
        """
        return self.load_from_database(symbol, timeframe, limit)
    
    def get_available_data(self) -> Dict:
        """
        查看数据库中已存储的数据概况
        
        Returns:
            Dict: 数据概况统计
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 按品种和时间周期统计
                cursor = conn.execute("""
                    SELECT symbol, timeframe, COUNT(*) as count, 
                           MIN(datetime) as earliest, MAX(datetime) as latest
                    FROM price_data
                    GROUP BY symbol, timeframe
                    ORDER BY symbol, timeframe
                """)
                
                data_summary = {}
                for symbol, timeframe, count, earliest, latest in cursor.fetchall():
                    if symbol not in data_summary:
                        data_summary[symbol] = {}
                    
                    data_summary[symbol][timeframe] = {
                        'count': count,
                        'earliest': earliest,
                        'latest': latest
                    }
                
                # 总体统计
                cursor = conn.execute("SELECT COUNT(*) FROM price_data")
                total_records = cursor.fetchone()[0]
                
                return {
                    'total_records': total_records,
                    'data_by_symbol_timeframe': data_summary
                }
                
        except Exception as e:
            print(f"❌ 获取数据概况失败: {e}")
            return {'total_records': 0, 'data_by_symbol_timeframe': {}}

def download_data_by_date_range(client, symbol, timeframe, start_date, end_date):
    """按日期范围下载数据"""
    print(f"🗓️  按日期范围下载 {symbol} {timeframe} 数据")
    print(f"📅 日期范围: {start_date} ~ {end_date}")
    print("-" * 50)
    
    try:
        df = client.get_forex_data(symbol, timeframe, start_date=start_date, end_date=end_date)
        
        if not df.empty:
            # 保存到数据库
            client.save_to_database(df, symbol, timeframe)
            
            # 统计信息
            actual_start = df['datetime'].min()
            actual_end = df['datetime'].max()
            latest_price = df['close'].iloc[-1]
            
            print(f"✅ 成功下载 {len(df)} 根K线")
            print(f"📅 实际时间范围: {actual_start} ~ {actual_end}")
            print(f"💰 最新价格: {latest_price:.5f}")
            
            return df
        else:
            print(f"❌ 未获取到数据")
            return pd.DataFrame()
            
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        return pd.DataFrame()

def download_data_by_year(client, symbol, timeframe, year):
    """按年份下载数据"""
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    return download_data_by_date_range(client, symbol, timeframe, start_date, end_date)

def download_data_batch(client, symbol, timeframes, size):
    """批量下载多时间周期数据"""
    print(f"🚀 开始批量下载 {symbol} 数据")
    print(f"📋 时间周期: {', '.join(timeframes)}")
    print(f"📊 每周期数量: {size} 根K线")
    print("-" * 50)
    
    total_downloaded = 0
    successful_downloads = []
    failed_downloads = []
    
    for i, timeframe in enumerate(timeframes, 1):
        print(f"\n[{i}/{len(timeframes)}] 📥 下载 {timeframe} 数据...")
        
        try:
            df = client.get_forex_data(symbol, timeframe, size)
            
            if not df.empty:
                # 保存到数据库
                client.save_to_database(df, symbol, timeframe)
                
                # 统计信息
                date_range = f"{df['datetime'].min()} ~ {df['datetime'].max()}"
                latest_price = df['close'].iloc[-1]
                
                print(f"✅ {timeframe}: {len(df)} 根K线")
                print(f"   📅 时间范围: {date_range}")
                print(f"   💰 最新价格: {latest_price:.5f}")
                
                total_downloaded += len(df)
                successful_downloads.append({
                    'timeframe': timeframe,
                    'count': len(df),
                    'range': date_range
                })
            else:
                print(f"❌ {timeframe}: 未获取到数据")
                failed_downloads.append(timeframe)
                
        except Exception as e:
            print(f"❌ {timeframe}: 下载失败 - {e}")
            failed_downloads.append(timeframe)
    
    # 下载总结
    print("\n" + "="*50)
    print("📈 下载总结:")
    print(f"✅ 成功: {len(successful_downloads)} 个时间周期")
    print(f"❌ 失败: {len(failed_downloads)} 个时间周期")
    print(f"📊 总计下载: {total_downloaded:,} 根K线")
    
    if failed_downloads:
        print(f"⚠️  失败的时间周期: {', '.join(failed_downloads)}")
    
    return successful_downloads, failed_downloads

def analyze_data_quality(client, symbol="EUR/USD", timeframe="15min", min_records=70):
    """
    分析数据质量，识别需要修复的日期
    
    Args:
        client: TwelveDataClient实例
        symbol: 交易品种
        timeframe: 时间周期
        min_records: 最少记录数阈值
        
    Returns:
        Dict: 包含严重缺失和中等缺失日期的字典
    """
    print(f"📊 分析 {symbol} {timeframe} 数据质量...")
    
    try:
        import sqlite3
        import pandas as pd
        
        with sqlite3.connect(client.db_path) as conn:
            # 查询低于阈值的工作日
            query = """
                SELECT 
                  DATE(datetime) as date,
                  strftime('%w', datetime) as weekday,
                  COUNT(*) as record_count
                FROM price_data 
                WHERE symbol=? AND timeframe=?
                  AND strftime('%w', datetime) NOT IN ('0','6')  -- 排除周末
                GROUP BY DATE(datetime)
                HAVING COUNT(*) < ?
                ORDER BY record_count ASC, date;
            """
            
            df = pd.read_sql_query(query, conn, params=(symbol, timeframe, min_records))
            
            if df.empty:
                print(f"✅ 所有工作日的数据质量均>={min_records}记录，无需修复!")
                return {"severe": [], "moderate": [], "total": 0}
            
            # 按严重程度分类
            severe_df = df[df['record_count'] < 40]  # 严重缺失
            moderate_df = df[(df['record_count'] >= 40) & (df['record_count'] < min_records)]  # 中等缺失
            
            severe_dates = severe_df['date'].tolist()
            moderate_dates = moderate_df['date'].tolist()
            
            print(f"发现 {len(df)} 个工作日数据质量需要改善")
            print(f"严重缺失 (<40记录): {len(severe_dates)} 天")
            print(f"中等缺失 (40-{min_records}记录): {len(moderate_dates)} 天")
            
            return {
                "severe": severe_dates,
                "moderate": moderate_dates,
                "total": len(df),
                "severe_details": severe_df.to_dict('records'),
                "moderate_details": moderate_df.to_dict('records')
            }
            
    except Exception as e:
        print(f"❌ 数据质量分析失败: {e}")
        return {"severe": [], "moderate": [], "total": 0}

def fix_missing_data_batch(client, problem_dates, symbol="EUR/USD", timeframe="15min"):
    """
    批量修复缺失数据
    
    Args:
        client: TwelveDataClient实例  
        problem_dates: 问题日期列表
        symbol: 交易品种
        timeframe: 时间周期
        
    Returns:
        Dict: 修复结果统计
    """
    print(f"🔧 开始批量修复 {len(problem_dates)} 个日期的数据...")
    print("=" * 60)
    
    from datetime import datetime, timedelta
    import time
    
    success_count = 0
    fail_count = 0
    total_added = 0
    
    for i, date_str in enumerate(problem_dates, 1):
        print(f"\n[{i}/{len(problem_dates)}] 修复 {date_str}...")
        
        try:
            # 创建时间窗口：前后各1天
            target_date = datetime.strptime(date_str, '%Y-%m-%d')
            start_date = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
            end_date = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
            
            print(f"   📅 下载时间窗口: {start_date} ~ {end_date}")
            
            # 获取数据
            df = client.get_forex_data(symbol, timeframe, start_date=start_date, end_date=end_date)
            
            if not df.empty:
                # 保存数据
                client.save_to_database(df, symbol, timeframe)
                
                # 验证修复效果：检查目标日期的记录数
                import sqlite3
                with sqlite3.connect(client.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM price_data 
                        WHERE symbol=? AND timeframe=? AND DATE(datetime)=?
                    """, (symbol, timeframe, date_str))
                    new_count = cursor.fetchone()[0]
                
                print(f"   ✅ 修复完成，目标日期现有 {new_count} 记录")
                success_count += 1
                total_added += len(df)
            else:
                print(f"   ❌ 未获取到数据")
                fail_count += 1
                
        except Exception as e:
            print(f"   ❌ 修复失败: {e}")
            fail_count += 1
        
        # API限制：每7次调用后暂停60秒（保守策略）
        if i % 7 == 0 and i < len(problem_dates):
            print(f"\n⏳ API限制保护，暂停60秒... ({i}/{len(problem_dates)} 已处理)")
            time.sleep(60)
    
    print(f"\n" + "=" * 60)
    print(f"🎉 批量修复完成!")
    print(f"✅ 成功修复: {success_count} 个日期")
    print(f"❌ 修复失败: {fail_count} 个日期") 
    print(f"📊 总计添加: {total_added:,} 条记录")
    
    return {
        "success": success_count,
        "failed": fail_count,
        "total_added": total_added
    }

def validate_fix_results(client, symbol="EUR/USD", timeframe="15min", min_records=70):
    """
    验证修复结果
    
    Args:
        client: TwelveDataClient实例
        symbol: 交易品种  
        timeframe: 时间周期
        min_records: 最少记录数阈值
        
    Returns:
        Dict: 修复后的质量统计
    """
    print(f"🔍 验证修复结果...")
    
    # 重新分析数据质量
    quality_report = analyze_data_quality(client, symbol, timeframe, min_records)
    
    try:
        import sqlite3
        with sqlite3.connect(client.db_path) as conn:
            # 统计总体数据质量
            cursor = conn.execute("""
                SELECT COUNT(*) as total_days,
                       AVG(record_count) as avg_records,
                       MIN(record_count) as min_records,
                       MAX(record_count) as max_records
                FROM (
                    SELECT DATE(datetime) as date, COUNT(*) as record_count
                    FROM price_data 
                    WHERE symbol=? AND timeframe=?
                      AND strftime('%w', datetime) NOT IN ('0','6')
                    GROUP BY DATE(datetime)
                )
            """, (symbol, timeframe))
            
            stats = cursor.fetchone()
            
            # 按质量等级分类统计
            cursor = conn.execute("""
                SELECT 
                    CASE 
                        WHEN record_count >= 85 THEN 'excellent'
                        WHEN record_count >= 70 THEN 'good'  
                        WHEN record_count >= 40 THEN 'fair'
                        ELSE 'poor'
                    END as quality_grade,
                    COUNT(*) as day_count
                FROM (
                    SELECT DATE(datetime) as date, COUNT(*) as record_count
                    FROM price_data 
                    WHERE symbol=? AND timeframe=?
                      AND strftime('%w', datetime) NOT IN ('0','6')
                    GROUP BY DATE(datetime)
                )
                GROUP BY quality_grade;
            """, (symbol, timeframe))
            
            quality_breakdown = {row[0]: row[1] for row in cursor.fetchall()}
            
            print(f"\n📊 修复后数据质量报告:")
            print(f"总工作日数: {stats[0]:,}")
            print(f"平均记录数: {stats[1]:.1f}")
            print(f"记录数范围: {stats[2]} - {stats[3]}")
            print(f"\n质量等级分布:")
            print(f"  优秀 (>=85记录): {quality_breakdown.get('excellent', 0):,} 天")
            print(f"  良好 (70-84记录): {quality_breakdown.get('good', 0):,} 天")
            print(f"  一般 (40-69记录): {quality_breakdown.get('fair', 0):,} 天")  
            print(f"  较差 (<40记录): {quality_breakdown.get('poor', 0):,} 天")
            
            # 计算质量百分比
            total_days = stats[0] or 1
            good_days = quality_breakdown.get('excellent', 0) + quality_breakdown.get('good', 0)
            quality_percentage = (good_days / total_days) * 100
            
            print(f"\n🎯 数据质量达标率: {quality_percentage:.1f}% (>=70记录)")
            
            return {
                "total_days": stats[0],
                "avg_records": stats[1],
                "quality_breakdown": quality_breakdown,
                "quality_percentage": quality_percentage,
                "remaining_problems": quality_report["total"]
            }
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return {}

def main():
    """通用批量K线数据下载工具"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='多时间周期K线数据批量下载工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 下载2000根日线数据
  python3 twelve_data_client.py --timeframe 1day --size 2000
  
  # 指定日期范围下载
  python3 twelve_data_client.py --timeframe 4h --start-date 2020-01-01 --end-date 2020-12-31
  
  # 下载指定年份数据
  python3 twelve_data_client.py --timeframe 4h --year 2020
  
  # 从2020年开始下载到现在
  python3 twelve_data_client.py --timeframe 4h --from-2020
  
  # 下载多个时间周期，每个1000根K线
  python3 twelve_data_client.py --timeframes 15min,1h,4h,1day --size 1000
  
  # 下载所有支持的时间周期，最大数据量
  python3 twelve_data_client.py --all --size 5000
  
  # 只显示数据库统计信息
  python3 twelve_data_client.py --show-stats
  
  # 地毯式修复所有缺失数据 (推荐)
  python3 twelve_data_client.py --fix-data
  
  # 只修复严重缺失的数据 (<40记录)
  python3 twelve_data_client.py --fix-severe
  
  # 只验证数据质量，不修复
  python3 twelve_data_client.py --validate-only
  
  # 设置修复阈值为80记录
  python3 twelve_data_client.py --fix-data --min-records 80
  
  # 使用自定义API密钥
  python3 twelve_data_client.py --api-key your-key --timeframe 1day --size 2000
        """
    )
    
    parser.add_argument('--api-key', default="8ae7370c143b4751a4c8d1b426f0dcb7",
                       help='Twelve Data API密钥 (已内置默认密钥)')
    parser.add_argument('--symbol', '-s', default='EUR/USD', 
                       help='交易品种 (默认: EUR/USD)')
    parser.add_argument('--timeframe', '-t', 
                       help='单个时间周期 (1min, 5min, 15min, 1h, 4h, 1day, 1week)')
    parser.add_argument('--timeframes', '-T', 
                       help='多个时间周期，逗号分隔 (如: 1min,5min,15min,1h,4h,1day)')
    parser.add_argument('--all', '-a', action='store_true',
                       help='下载所有支持的时间周期')
    parser.add_argument('--size', '-n', type=int, default=5000,
                       help='每个时间周期的K线数量 (默认: 5000, 最大: 5000)')
    parser.add_argument('--show-stats', action='store_true',
                       help='显示数据库统计信息')
    
    # 快捷任务：最近一年 1min 分段下载
    parser.add_argument('--last-year-chunked', action='store_true',
                       help='下载最近一年数据（建议配合 --timeframe 1min，按窗口分段入库）')
    parser.add_argument('--chunk-days', type=float, default=3.5,
                       help='分段窗口天数，≈5000根/次（默认: 3.0）')
    
    # 日期相关参数
    parser.add_argument('--start-date', '-sd', 
                       help='开始日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--end-date', '-ed', 
                       help='结束日期 (格式: YYYY-MM-DD)')
    parser.add_argument('--year', '-y', type=int,
                       help='指定年份下载 (如: 2020)')
    parser.add_argument('--from-2020', action='store_true',
                       help='从2020年开始下载到现在的所有数据')
    
    # 数据修复相关参数
    parser.add_argument('--fix-data', action='store_true',
                       help='修复缺失数据模式')
    parser.add_argument('--fix-severe', action='store_true',
                       help='只修复严重缺失的数据 (<40记录)')
    parser.add_argument('--min-records', type=int, default=70,
                       help='数据质量阈值，低于此值的工作日将被修复 (默认: 70)')
    parser.add_argument('--validate-only', action='store_true',
                       help='只验证数据质量，不进行修复')
    parser.add_argument('--auto-confirm', action='store_true',
                       help='自动确认修复操作，无需用户输入')
    
    args = parser.parse_args()
    
    # 验证参数
    if args.size > 5000 or args.size < 1:
        print("❌ 错误: size参数必须在1-5000范围内")
        return 1
    
    # 验证日期参数
    date_params_count = sum([bool(args.start_date), bool(args.year), bool(args.from_2020)])
    if date_params_count > 1:
        print("❌ 错误: 不能同时使用多个日期参数 (--start-date, --year, --from-2020)")
        return 1
    
    if args.start_date and not args.end_date:
        print("❌ 错误: 使用 --start-date 时必须同时提供 --end-date")
        return 1
    
    if args.end_date and not args.start_date:
        print("❌ 错误: 使用 --end-date 时必须同时提供 --start-date")
        return 1
        
    if args.start_date and not validate_date_format(args.start_date):
        print("❌ 错误: start-date 格式错误，请使用 YYYY-MM-DD 格式")
        return 1
        
    if args.end_date and not validate_date_format(args.end_date):
        print("❌ 错误: end-date 格式错误，请使用 YYYY-MM-DD 格式")
        return 1
    
    print("🤖 多时间周期K线数据批量下载工具")
    print("=" * 60)
    
    # 创建客户端
    try:
        client = TwelveDataClient(args.api_key)
    except Exception as e:
        print(f"❌ 客户端初始化失败: {e}")
        return 1
    
    # 显示数据库统计
    if args.show_stats:
        print("\n📊 数据库统计信息:")
        overview = client.get_available_data()
        print(f"总记录数: {overview['total_records']:,}")
        
        if overview['data_by_symbol_timeframe']:
            for symbol, timeframes in overview['data_by_symbol_timeframe'].items():
                print(f"\n💱 {symbol}:")
                for tf, info in timeframes.items():
                    print(f"  {tf: <8}: {info['count']:>6} 条记录 ({info['earliest']} ~ {info['latest']})")
        else:
            print("📝 数据库为空")
        
        if not any([args.timeframe, args.timeframes, args.all, args.fix_data, args.fix_severe, args.validate_only]):
            return 0
    
    # 数据修复模式
    if args.fix_data or args.fix_severe or args.validate_only:
        tf = args.timeframe or '1min'
        print(f"\n🔧 数据修复模式: {args.symbol} {tf}")
        print("=" * 60)
        
        # 数据质量分析
        quality_report = analyze_data_quality(client, args.symbol, tf, args.min_records)
        
        if args.validate_only:
            # 只验证模式
            validate_fix_results(client, args.symbol, tf, args.min_records)
            return 0
        
        # 确定要修复的日期
        if args.fix_severe:
            # 只修复严重缺失
            problem_dates = quality_report["severe"]
            print(f"\n🚨 严重缺失修复模式: {len(problem_dates)} 个日期")
        else:
            # 修复所有问题数据
            problem_dates = quality_report["severe"] + quality_report["moderate"]
            print(f"\n🔧 全面修复模式: {len(problem_dates)} 个日期")
        
        if not problem_dates:
            print("✅ 没有需要修复的数据!")
            return 0
        
        # 用户确认
        print(f"\n⚠️  将要修复 {len(problem_dates)} 个工作日的数据")
        print(f"预计API调用: {len(problem_dates)} 次")
        print(f"预计时间: {len(problem_dates) // 7 + 1} 分钟 (每7次调用暂停60秒)")
        
        if not args.auto_confirm:
            response = input("\n是否继续? (y/N): ").strip().lower()
            if response not in ['y', 'yes']:
                print("❌ 用户取消修复")
                return 0
        else:
            print("\n✅ 自动确认模式，开始修复...")
        
        # 执行修复
        fix_result = fix_missing_data_batch(client, problem_dates, args.symbol, tf)
        
        # 验证修复结果
        print("\n" + "=" * 60)
        validate_fix_results(client, args.symbol, tf, args.min_records)
        
        return 0 if fix_result["failed"] == 0 else 1
    
    # 确定要下载的时间周期
    all_timeframes = ["1min", "5min", "15min", "30min", "1h", "2h", "4h", "1day", "1week"]
    
    if args.all:
        timeframes = all_timeframes
    elif args.timeframes:
        timeframes = [tf.strip() for tf in args.timeframes.split(',')]
        # 验证时间周期有效性
        invalid_tfs = [tf for tf in timeframes if tf not in all_timeframes]
        if invalid_tfs:
            print(f"❌ 错误: 无效的时间周期: {', '.join(invalid_tfs)}")
            print(f"✅ 支持的时间周期: {', '.join(all_timeframes)}")
            return 1
    elif args.timeframe:
        if args.timeframe not in all_timeframes:
            print(f"❌ 错误: 无效的时间周期: {args.timeframe}")
            print(f"✅ 支持的时间周期: {', '.join(all_timeframes)}")
            return 1
        timeframes = [args.timeframe]
    else:
        print("❌ 错误: 请指定要下载的时间周期 (--timeframe, --timeframes, 或 --all)")
        return 1
    
    # 特殊快捷任务：最近一年分段下载
    if args.last_year_chunked:
        tf = args.timeframe or '1min'
        if tf != '1min':
            print(f"⚠️ 提示: 当前设置 timeframe={tf}，该任务主要面向 1min 周期。")
        try:
            client.download_last_year_in_chunks(symbol=args.symbol, timeframe=tf, chunk_days=args.chunk_days)
            return 0
        except Exception as e:
            print(f"❌ 分段下载失败: {e}")
            return 1

    # 执行下载
    try:
        successful = []
        failed = []
        
        # 根据日期参数选择下载策略
        if args.start_date and args.end_date:
            # 日期范围下载
            for timeframe in timeframes:
                result_df = download_data_by_date_range(client, args.symbol, timeframe, args.start_date, args.end_date)
                if not result_df.empty:
                    successful.append(timeframe)
                else:
                    failed.append(timeframe)
        elif args.year:
            # 年份下载
            for timeframe in timeframes:
                result_df = download_data_by_year(client, args.symbol, timeframe, args.year)
                if not result_df.empty:
                    successful.append(timeframe)
                else:
                    failed.append(timeframe)
        elif args.from_2020:
            # 从2020年开始分年下载
            current_year = datetime.now().year
            for timeframe in timeframes:
                print(f"\n🗓️  下载 {timeframe} 从2020年到现在的所有数据")
                year_success = 0
                for year in range(2020, current_year + 1):
                    print(f"  📅 下载 {year} 年数据...")
                    result_df = download_data_by_year(client, args.symbol, timeframe, year)
                    if not result_df.empty:
                        year_success += 1
                if year_success > 0:
                    successful.append(f"{timeframe}({year_success}年)")
                else:
                    failed.append(timeframe)
        else:
            # 传统批量下载
            successful, failed = download_data_batch(client, args.symbol, timeframes, args.size)
        
        # 最终统计
        if args.show_stats and (successful or failed):
            print("\n📈 更新后数据库统计:")
            final_overview = client.get_available_data()
            print(f"总记录数: {final_overview['total_records']:,}")
        
        print("\n🎉 下载完成!")
        if successful:
            print(f"✅ 成功: {len(successful)} 项")
        if failed:
            print(f"❌ 失败: {len(failed)} 项")
        return 0 if not failed else 1
        
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断下载")
        return 1
    except Exception as e:
        print(f"\n❌ 批量下载失败: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
