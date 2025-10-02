#!/usr/bin/env python3
"""
PA交互式图表会话管理器 - 支持快速更新和动态数据加载
实现2-4秒响应时间的交互式图表更新
"""

import time
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from datetime import datetime, timedelta

from .pa_data_reader import PA_DataReader
from .pa_chart_display import PA_ChartDisplay
from .pa_pattern_analyzer import PA_PatternAnalyzer


class PA_ChartSession:
    """交互式图表会话管理器 - 优化响应速度和用户体验"""
    
    def __init__(self, symbol: str = "EUR/USD", timeframe: str = "15min"):
        """
        初始化交互式会话
        
        Args:
            symbol: 交易品种
            timeframe: 时间周期
        """
        self.symbol = symbol
        self.timeframe = timeframe
        
        # 核心组件
        self.data_reader = PA_DataReader()
        self.chart_display = None
        self.pattern_analyzer = PA_PatternAnalyzer()
        
        # 缓存管理
        self.data_cache = None          # K线数据缓存
        self.chart_data_cache = None    # 图表格式数据缓存
        self.analysis_cache = {}        # 分析结果缓存
        
        # 状态管理
        self.current_range = {'start': 0, 'count': 1000}  # 当前数据范围
        self.indicators = {}             # 已添加的指标
        self.overlays = {}               # 叠加层（线、标记等）
        self.last_update_time = None    # 最后更新时间
        
        print(f"📊 交互式图表会话已创建 ({symbol} {timeframe})")
    
    def show(self, count: int = 1000, analyze: bool = True) -> None:
        """
        首次显示图表或完全刷新
        
        Args:
            count: 显示的K线数量
            analyze: 是否自动进行PA分析
        """
        start_time = time.time()
        print(f"⏳ 正在加载图表...")
        
        # 1. 获取数据（使用优化的默认值）
        self.data_cache = self.data_reader.get_recent_data(
            symbol=self.symbol,
            timeframe=self.timeframe,
            count=count
        )
        
        if self.data_cache.empty:
            print("❌ 无数据可显示")
            return
        
        # 2. 格式化为图表数据
        self.chart_data_cache = self.data_reader.format_for_chart(self.data_cache)
        
        # 3. 创建或重建图表
        if self.chart_display is None:
            self.chart_display = PA_ChartDisplay()
        
        chart = self.chart_display.create_chart(
            title=f"{self.symbol} {self.timeframe} - 交互式图表"
        )
        self.chart_display.load_data(self.chart_data_cache)
        
        # 4. 自动PA分析（可选）
        if analyze:
            self._auto_analyze()
        
        # 5. 显示图表
        self.chart_display.show_chart(block=False)
        
        # 记录状态
        self.current_range['count'] = count
        self.last_update_time = time.time()
        
        elapsed = time.time() - start_time
        print(f"✅ 图表已显示 (耗时: {elapsed:.1f}秒)")
        print(f"   数据范围: {self.data_cache['datetime'].min()} ~ {self.data_cache['datetime'].max()}")
        print(f"   K线数量: {len(self.data_cache)}")
    
    def update(self, **kwargs) -> None:
        """
        快速更新图表（使用缓存）
        
        支持的更新参数:
            - add_lines: 添加水平线 [(price, color, label), ...]
            - add_markers: 添加标记 [(index, position, color, text), ...]
            - indicators: 更新指标 {'MA': {'period': 50}, ...}
            - analyze: 重新进行PA分析
        """
        if self.data_cache is None:
            print("❌ 请先调用 show() 显示图表")
            return
        
        start_time = time.time()
        print(f"⏳ 正在更新图表...")
        
        # 快速重建图表（使用缓存数据）
        chart = self.chart_display.create_chart(
            title=f"{self.symbol} {self.timeframe} - 交互式图表 (已更新)"
        )
        self.chart_display.load_data(self.chart_data_cache)
        
        # 应用更新
        if 'add_lines' in kwargs:
            for line_config in kwargs['add_lines']:
                price, color, label = line_config
                self._add_horizontal_line(price, color, label)
        
        if 'add_markers' in kwargs:
            for marker_config in kwargs['add_markers']:
                self._add_marker(*marker_config)
        
        if 'indicators' in kwargs:
            self._update_indicators(kwargs['indicators'])
        
        if kwargs.get('analyze', False):
            self._auto_analyze()
        
        # 重新应用所有缓存的叠加层
        self._reapply_overlays()
        
        # 显示更新后的图表
        self.chart_display.show_chart(block=False)
        
        elapsed = time.time() - start_time
        print(f"✅ 图表已更新 (耗时: {elapsed:.1f}秒)")
    
    def load_more_history(self, count: int = 500) -> None:
        """
        动态加载更多历史数据
        
        Args:
            count: 额外加载的K线数量
        """
        start_time = time.time()
        print(f"⏳ 正在加载更多历史数据...")
        
        # 计算新的数据范围
        new_total = self.current_range['count'] + count
        
        # 获取扩展的数据集
        extended_data = self.data_reader.get_recent_data(
            symbol=self.symbol,
            timeframe=self.timeframe,
            count=new_total
        )
        
        if extended_data.empty:
            print("❌ 无更多历史数据")
            return
        
        # 更新缓存
        self.data_cache = extended_data
        self.chart_data_cache = self.data_reader.format_for_chart(extended_data)
        self.current_range['count'] = len(extended_data)
        
        # 快速重建图表
        self._quick_rebuild()
        
        elapsed = time.time() - start_time
        added = len(extended_data) - (self.current_range['count'] - count)
        print(f"✅ 已加载 {added} 根历史K线 (总计: {len(extended_data)}, 耗时: {elapsed:.1f}秒)")
    
    def load_date_range(self, start_date: str, end_date: str) -> None:
        """
        加载指定日期范围的数据
        
        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
        """
        start_time = time.time()
        print(f"⏳ 正在加载 {start_date} 至 {end_date} 的数据...")
        
        # 获取指定范围数据
        range_data = self.data_reader.get_data_by_range(
            symbol=self.symbol,
            timeframe=self.timeframe,
            start_date=start_date,
            end_date=end_date
        )
        
        if range_data.empty:
            print("❌ 指定范围无数据")
            return
        
        # 更新缓存
        self.data_cache = range_data
        self.chart_data_cache = self.data_reader.format_for_chart(range_data)
        self.current_range['count'] = len(range_data)
        
        # 快速重建图表
        self._quick_rebuild()
        
        elapsed = time.time() - start_time
        print(f"✅ 已加载指定范围数据 ({len(range_data)} 根K线, 耗时: {elapsed:.1f}秒)")
    
    def update_indicator(self, name: str, **params) -> None:
        """
        更新单个指标
        
        Args:
            name: 指标名称 (如 'MA', 'RSI', 'MACD')
            **params: 指标参数
        """
        print(f"⏳ 正在更新指标 {name}...")
        
        # 保存指标配置
        self.indicators[name] = params
        
        # 快速更新
        self.update(indicators={name: params})
    
    def add_support_resistance(self, levels: List[Tuple[float, str]]) -> None:
        """
        添加支撑阻力线
        
        Args:
            levels: [(价格, 描述), ...] 如 [(1.0800, '关键支撑'), (1.0900, '强阻力')]
        """
        lines = [(price, 'green' if '支撑' in desc else 'red', desc) 
                 for price, desc in levels]
        self.update(add_lines=lines)
    
    def clear_overlays(self) -> None:
        """清除所有叠加层"""
        self.overlays.clear()
        self.indicators.clear()
        print("✅ 已清除所有叠加层")
    
    # ========== 私有方法 ==========
    
    def _auto_analyze(self) -> None:
        """自动进行PA分析并标注"""
        if self.data_cache is None:
            return
        
        print("🔍 正在进行PA分析...")
        
        # 使用PA分析器
        analysis_result = self.pattern_analyzer.analyze_pattern(
            self.data_cache,
            timeframe=self.timeframe
        )
        
        # 缓存分析结果
        self.analysis_cache = analysis_result
        
        # 添加分析标注
        if analysis_result and 'trading_signals' in analysis_result:
            self.chart_display.add_pattern_annotation(analysis_result)
            signal_count = len(analysis_result.get('trading_signals', []))
            print(f"✅ 已添加 {signal_count} 个PA信号标注")
    
    def _quick_rebuild(self) -> None:
        """快速重建图表（内部使用）"""
        chart = self.chart_display.create_chart(
            title=f"{self.symbol} {self.timeframe} - 交互式图表"
        )
        self.chart_display.load_data(self.chart_data_cache)
        
        # 重新应用分析结果
        if self.analysis_cache:
            self.chart_display.add_pattern_annotation(self.analysis_cache)
        
        # 重新应用叠加层
        self._reapply_overlays()
        
        self.chart_display.show_chart(block=False)
    
    def _add_horizontal_line(self, price: float, color: str, label: str) -> None:
        """添加水平线到叠加层"""
        if 'lines' not in self.overlays:
            self.overlays['lines'] = []
        self.overlays['lines'].append((price, color, label))
        
        # 直接在图表上添加
        if self.chart_display and self.chart_display.chart:
            self.chart_display.chart.horizontal_line(
                price, 
                color=color, 
                width=2, 
                style='solid'
            )
    
    def _add_marker(self, index: int, position: str, color: str, text: str) -> None:
        """添加标记到叠加层"""
        if 'markers' not in self.overlays:
            self.overlays['markers'] = []
        self.overlays['markers'].append((index, position, color, text))
        
        # 获取对应时间
        if 0 <= index < len(self.data_cache):
            datetime_obj = self.data_cache.iloc[index]['datetime']
            if self.chart_display and self.chart_display.chart:
                self.chart_display.chart.marker(
                    time=datetime_obj,
                    position=position,
                    color=color,
                    shape='circle',
                    text=text
                )
    
    def _update_indicators(self, indicators: Dict) -> None:
        """更新技术指标"""
        # 这里可以扩展实现各种技术指标的计算和显示
        # 当前版本仅保存配置，实际计算可根据需要添加
        self.indicators.update(indicators)
        print(f"✅ 已更新指标配置: {list(indicators.keys())}")
    
    def _reapply_overlays(self) -> None:
        """重新应用所有叠加层"""
        # 重新应用水平线
        if 'lines' in self.overlays:
            for price, color, label in self.overlays['lines']:
                self._add_horizontal_line(price, color, label)
        
        # 重新应用标记
        if 'markers' in self.overlays:
            for index, position, color, text in self.overlays['markers']:
                self._add_marker(index, position, color, text)
    
    def get_status(self) -> Dict:
        """获取会话状态信息"""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'data_count': len(self.data_cache) if self.data_cache is not None else 0,
            'cache_size_mb': self._estimate_cache_size(),
            'indicators': list(self.indicators.keys()),
            'overlays_count': sum(len(v) for v in self.overlays.values()),
            'last_update': self.last_update_time
        }
    
    def _estimate_cache_size(self) -> float:
        """估算缓存占用内存（MB）"""
        if self.data_cache is None:
            return 0.0
        
        # 粗略估算：每行约200字节
        bytes_estimate = len(self.data_cache) * 200
        return bytes_estimate / (1024 * 1024)


def demo_interactive_session():
    """演示交互式图表会话的使用"""
    print("="*60)
    print("🎯 交互式图表会话演示")
    print("="*60)
    
    # 创建会话
    session = PA_ChartSession()
    
    # 初始显示
    print("\n1️⃣ 首次显示图表")
    session.show(count=500)
    
    # 模拟用户交互
    import time
    time.sleep(2)
    
    print("\n2️⃣ 添加支撑阻力线")
    session.add_support_resistance([
        (1.0800, '关键支撑'),
        (1.0850, '次要支撑'),
        (1.0900, '主要阻力')
    ])
    
    time.sleep(2)
    
    print("\n3️⃣ 加载更多历史数据")
    session.load_more_history(300)
    
    print("\n4️⃣ 查看会话状态")
    status = session.get_status()
    print(f"   当前数据: {status['data_count']} 根K线")
    print(f"   缓存大小: {status['cache_size_mb']:.2f} MB")
    print(f"   叠加层数: {status['overlays_count']}")
    
    print("\n✅ 演示完成！")


if __name__ == "__main__":
    demo_interactive_session()