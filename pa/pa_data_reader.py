#!/usr/bin/env python3
"""
PA数据读取器 - 基于现有TwelveDataClient的数据读取封装
专门为价格行为分析优化的数据读取接口
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import sqlite3
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from twelve_data_client import TwelveDataClient


class PA_DataReader:
    """价格行为分析专用数据读取器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据读取器
        
        Args:
            db_path: 数据库路径，默认使用项目根目录下的data/forex_data.db
        """
        if db_path is None:
            # 默认使用项目根目录下的数据库
            project_root = os.path.dirname(os.path.dirname(__file__))
            db_path = os.path.join(project_root, "data", "forex_data.db")
        
        self.db_path = db_path
        self.client = TwelveDataClient()
        
        # 验证数据库存在
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
    
    def get_recent_data(self, 
                       symbol: str = "EUR/USD",
                       timeframe: str = "15min", 
                       count: int = 1000) -> pd.DataFrame:
        """
        获取最近的K线数据
        
        Args:
            symbol: 交易品种
            timeframe: 时间周期
            count: 数据数量
            
        Returns:
            pandas.DataFrame: OHLC数据，按时间正序排列
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                query = """
                    SELECT datetime, open, high, low, close, volume
                    FROM price_data 
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY datetime DESC
                    LIMIT ?
                """
                df = pd.read_sql_query(query, conn, params=(symbol, timeframe, count))
                
                if df.empty:
                    print(f"❌ 未找到数据: {symbol} {timeframe}")
                    return pd.DataFrame()
                
                # 转换数据类型
                df['datetime'] = pd.to_datetime(df['datetime'])
                for col in ['open', 'high', 'low', 'close']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # 按时间正序排列（用于分析）
                df = df.sort_values('datetime').reset_index(drop=True)
                
                print(f"✅ 获取 {symbol} {timeframe} 最近 {len(df)} 根K线")
                return df
                
        except Exception as e:
            print(f"❌ 数据读取失败: {e}")
            return pd.DataFrame()
    
    def get_data_by_range(self, 
                         symbol: str = "EUR/USD",
                         timeframe: str = "15min",
                         start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        """
        按日期范围获取K线数据
        
        Args:
            symbol: 交易品种
            timeframe: 时间周期
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            
        Returns:
            pandas.DataFrame: OHLC数据
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                if start_date and end_date:
                    query = """
                        SELECT datetime, open, high, low, close, volume
                        FROM price_data 
                        WHERE symbol = ? AND timeframe = ?
                        AND DATE(datetime) >= ? AND DATE(datetime) <= ?
                        ORDER BY datetime ASC
                    """
                    params = (symbol, timeframe, start_date, end_date)
                else:
                    # 如果没有指定日期范围，返回所有数据
                    query = """
                        SELECT datetime, open, high, low, close, volume
                        FROM price_data 
                        WHERE symbol = ? AND timeframe = ?
                        ORDER BY datetime ASC
                    """
                    params = (symbol, timeframe)
                
                df = pd.read_sql_query(query, conn, params=params)
                
                if not df.empty:
                    df['datetime'] = pd.to_datetime(df['datetime'])
                    for col in ['open', 'high', 'low', 'close']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    print(f"✅ 获取 {symbol} {timeframe} 数据: {len(df)} 根K线")
                    if not df.empty:
                        print(f"   时间范围: {df['datetime'].min()} ~ {df['datetime'].max()}")
                
                return df
                
        except Exception as e:
            print(f"❌ 数据读取失败: {e}")
            return pd.DataFrame()
    
    def get_sliding_windows(self, 
                           symbol: str = "EUR/USD",
                           timeframe: str = "15min",
                           window_size: int = 100,
                           step_size: int = 10,
                           start_date: str = None,
                           end_date: str = None) -> List[pd.DataFrame]:
        """
        获取滑动窗口数据集合，用于批量分析和回测
        
        Args:
            symbol: 交易品种
            timeframe: 时间周期
            window_size: 窗口大小（K线数量）
            step_size: 步长（每次移动的K线数量）
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            List[pd.DataFrame]: 滑动窗口数据列表
        """
        # 获取全部数据
        full_data = self.get_data_by_range(symbol, timeframe, start_date, end_date)
        
        if full_data.empty or len(full_data) < window_size:
            print(f"❌ 数据量不足，无法创建大小为 {window_size} 的滑动窗口")
            return []
        
        windows = []
        for i in range(0, len(full_data) - window_size + 1, step_size):
            window = full_data.iloc[i:i + window_size].copy().reset_index(drop=True)
            windows.append(window)
        
        print(f"✅ 创建 {len(windows)} 个滑动窗口 (窗口大小: {window_size}, 步长: {step_size})")
        return windows
    
    def format_for_chart(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        将DataFrame格式转换为lightweight-charts所需的格式
        
        Args:
            df: OHLC数据DataFrame
            
        Returns:
            pd.DataFrame: 图表数据格式 (columns: time, open, high, low, close)
        """
        if df.empty:
            return pd.DataFrame()
        
        # 直接使用必需的列，减少不必要的转换
        return df[['datetime', 'open', 'high', 'low', 'close']].rename(columns={'datetime': 'time'})
    
    def format_for_llm(self, df: pd.DataFrame, include_index: bool = True) -> str:
        """
        将DataFrame格式化为LLM分析所需的文本格式
        
        Args:
            df: OHLC数据DataFrame
            include_index: 是否包含索引编号
            
        Returns:
            str: 格式化的文本数据
        """
        if df.empty:
            return "无数据"
        
        lines = []
        lines.append("时间,开盘,最高,最低,收盘")
        
        for i, (_, row) in enumerate(df.iterrows()):
            if include_index:
                line = f"K{i+1:03d}: {row['datetime'].strftime('%H:%M')}, {row['open']:.5f}, {row['high']:.5f}, {row['low']:.5f}, {row['close']:.5f}"
            else:
                line = f"{row['datetime'].strftime('%H:%M')}, {row['open']:.5f}, {row['high']:.5f}, {row['low']:.5f}, {row['close']:.5f}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def get_data_info(self) -> Dict:
        """
        获取数据库中的数据概况
        
        Returns:
            Dict: 数据统计信息
        """
        return self.client.get_available_data()


def test_pa_data_reader():
    """测试PA数据读取器功能"""
    print("🧪 测试PA数据读取器")
    print("=" * 50)
    
    try:
        # 初始化读取器
        reader = PA_DataReader()
        
        # 测试获取最近数据
        recent_data = reader.get_recent_data(count=50)
        print(f"\n📊 最近50根K线:")
        if not recent_data.empty:
            print(f"   数据量: {len(recent_data)}")
            print(f"   时间范围: {recent_data['datetime'].min()} ~ {recent_data['datetime'].max()}")
            print(f"   最新价格: {recent_data['close'].iloc[-1]:.5f}")
        
        # 测试格式化功能
        chart_data = reader.format_for_chart(recent_data.head(5))
        print(f"\n📈 图表数据格式 (前5根):")
        for item in chart_data[:2]:
            print(f"   {item}")
        
        # 测试LLM格式化
        llm_data = reader.format_for_llm(recent_data.tail(5), include_index=True)
        print(f"\n🤖 LLM分析格式 (最后5根):")
        print(llm_data[:200] + "...")
        
        # 测试数据概况
        info = reader.get_data_info()
        print(f"\n📋 数据库概况:")
        print(f"   总记录数: {info.get('total_records', 0):,}")
        
        print(f"\n✅ PA数据读取器测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")


if __name__ == "__main__":
    test_pa_data_reader()