#!/usr/bin/env python3
"""
PA图表显示器 - 基于lightweight-charts-python的K线图表显示
支持LLM分析结果的可视化标注
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json

try:
    from lightweight_charts import Chart
except ImportError:
    print("❌ 请安装 lightweight-charts: pip install lightweight-charts")
    raise


class PA_ChartDisplay:
    """价格行为分析专用图表显示器"""
    
    def __init__(self, width: int = 1200, height: int = 600):
        """
        初始化图表显示器
        
        Args:
            width: 图表宽度
            height: 图表高度
        """
        self.width = width
        self.height = height
        self.chart = None
        self.candlestick_series = None
        self.current_data = []  # 存储当前图表数据，用于索引到时间戳的映射
    
    def create_chart(self, title: str = "价格行为分析") -> Chart:
        """
        创建基础K线图表
        
        Args:
            title: 图表标题
            
        Returns:
            Chart: 图表对象
        """
        self.chart = Chart(
            width=self.width,
            height=self.height,
            title=title
        )
        
        # Chart对象本身就是K线图，不需要额外创建candlestick_series
        self.candlestick_series = self.chart
        
        return self.chart
    
    def load_data(self, chart_data: pd.DataFrame) -> None:
        """
        加载K线数据到图表
        
        Args:
            chart_data: 格式化的图表数据DataFrame (columns: time, open, high, low, close, volume)
        """
        if not self.candlestick_series:
            raise Exception("请先创建图表")
        
        if chart_data.empty:
            print("❌ 无数据可加载")
            return
        
        # 保存当前数据用于索引映射 - 保持与图表数据相同的datetime格式
        self.current_data = []
        for _, row in chart_data.iterrows():
            self.current_data.append({
                'time': row['time'],  # 🚨 修复：使用datetime对象而不是时间戳
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        
        # 加载数据到图表
        self.candlestick_series.set(chart_data)
        print(f"✅ 已加载 {len(chart_data)} 根K线数据")
    
    def add_pattern_annotation(self, analysis_result: Dict) -> None:
        """
        根据PA策略分析结果添加图表标注 - 升级版支持Box和盈亏比
        
        Args:
            analysis_result: PA策略分析结果 
        """
        if not self.chart:
            print("❌ 请先创建图表")
            return
        
        if not self.current_data:
            print("❌ 请先加载图表数据")
            return
        
        try:
            # 处理PA策略信号
            trading_signals = analysis_result.get('trading_signals', [])
            combinations = analysis_result.get('combinations', [])
            
            # 兼容旧版本的signal_bars
            signal_bars = analysis_result.get('signal_bars', [])
            signal_bars_info = analysis_result.get('signal_bars_info', [])
            
            # 优先使用PA策略信号
            if trading_signals:
                # 尝试从分析结果中获取backtest_stats引用
                backtest_stats = analysis_result.get('_backtest_stats', None)
                self._add_pa_strategy_annotations(trading_signals, combinations, backtest_stats)
            elif signal_bars:
                self._add_legacy_annotations(signal_bars, signal_bars_info)
            else:
                print("⚠️ 未找到可显示的信号")
                return
                
        except Exception as e:
            print(f"❌ 标注失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _add_pa_strategy_annotations(self, trading_signals: list, combinations: list, backtest_stats=None) -> None:
        """
        添加PA策略信号标注和风险收益Box
        
        Args:
            trading_signals: PA策略信号列表
            combinations: 高级组合列表
            backtest_stats: PA回测统计系统（可选，用于查询历史交易结果）
        """
        print(f"🎯 添加PA策略标注 ({len(trading_signals)}个信号)...")
        
        # 统计计数器
        result_stats = {
            'target': 0,    # 止盈
            'stop_loss': 0, # 止损
            'pending': 0    # 待定/未完成
        }
        
        for signal in trading_signals:
            bar_index = signal['index']
            array_index = bar_index - 1 if bar_index > 0 else bar_index
            
            # 确保索引在有效范围内
            if 0 <= array_index < len(self.current_data):
                datetime_obj = self.current_data[array_index]['time']
                is_bullish = signal['is_bullish']
                label_text = signal['label_text']
                
                # 添加信号标记
                if is_bullish:
                    marker_color = 'green'
                    marker_shape = 'arrow_up'
                    position = 'below'
                else:
                    marker_color = 'red'
                    marker_shape = 'arrow_down'
                    position = 'above'
                
                self.chart.marker(
                    time=datetime_obj,
                    position=position,
                    color=marker_color,
                    shape=marker_shape,
                    text=label_text
                )
                
                # 添加风险收益Box并获取交易结果
                trade_result = self._add_risk_reward_box_with_result(
                    signal, datetime_obj, array_index, backtest_stats
                )
                
                # 更新统计计数
                if trade_result in result_stats:
                    result_stats[trade_result] += 1
                else:
                    result_stats['pending'] += 1
        
        # 计算胜率
        total_completed = result_stats['target'] + result_stats['stop_loss']
        win_rate = (result_stats['target'] / total_completed * 100) if total_completed > 0 else 0.0
        
        # 输出最终统计
        if total_completed > 0:
            print(f"✅ 已添加PA策略标注 (信号:{len(trading_signals)}个) "
                  f"共{result_stats['target']}个止盈, {result_stats['stop_loss']}个止损, "
                  f"{result_stats['pending']}个待定 胜率:{win_rate:.1f}%")
        else:
            print(f"✅ 已添加PA策略标注 (信号:{len(trading_signals)}个) 所有信号待定，无历史交易数据")
    
    def _add_risk_reward_box_with_result(self, signal: dict, datetime_obj, array_index: int, backtest_stats=None) -> str:
        """
        添加风险收益Box区域并返回交易结果 - 使用多层标注模拟PA策略的Box效果
        
        Args:
            signal: 信号字典
            datetime_obj: 时间对象
            array_index: 数组索引
            backtest_stats: PA回测统计系统
            
        Returns:
            str: 交易结果 ('target', 'stop_loss', 'pending')
        """
        # 先调用原来的Box绘制逻辑
        self._add_risk_reward_box(signal, datetime_obj, array_index)
        
        # 查询历史交易结果
        result = self._find_trade_result(signal, datetime_obj, backtest_stats)
        
        # 输出Box信息包含结果
        entry_price = signal['entry_price']
        stop_loss_price = signal['stop_loss_price']
        
        # 计算目标价格
        risk_pips = abs(entry_price - stop_loss_price)
        if signal['is_bullish']:
            target_price = entry_price + risk_pips * 2.0
        else:
            target_price = entry_price - risk_pips * 2.0
        
        # 转换结果为中文显示
        result_text = {
            'target': '止盈',
            'stop_loss': '止损',  
            'time_limit': '超时',
            'pending': '待定'
        }.get(result, '待定')
        
        print(f"✅ 已添加PA策略风格Box (入场:{entry_price:.5f}, 止损:{stop_loss_price:.5f}, 止盈:{target_price:.5f}) 结果: {result_text}")
        
        return result
    
    def _add_risk_reward_box(self, signal: dict, datetime_obj, array_index: int) -> None:
        """
        添加风险收益Box区域 - 使用多层标注模拟PA策略的Box效果
        
        Args:
            signal: 信号字典
            datetime_obj: 时间对象
            array_index: 数组索引
        """
        try:
            entry_price = signal['entry_price']
            stop_loss_price = signal['stop_loss_price']
            risk_amount = signal.get('risk_amount', 0)
            is_bullish = signal['is_bullish']
            
            # 计算目标价格（默认2:1盈亏比）
            risk_pips = abs(entry_price - stop_loss_price)
            if is_bullish:
                target_price = entry_price + risk_pips * 2.0
            else:
                target_price = entry_price - risk_pips * 2.0
            
            # 🎯 PA策略风格的Box效果实现 - 使用线段替代水平线
            
            # 计算线段的时间范围（8根K线宽度，避免臃肿）
            segment_width = 8
            segment_end_index = min(array_index + segment_width, len(self.current_data) - 1)
            segment_end_datetime = self.current_data[segment_end_index]['time']
            
            # 1. 入场价格线段（蓝色实线，较粗）
            try:
                self.chart.trend_line(
                    start_time=datetime_obj,
                    start_value=entry_price,
                    end_time=segment_end_datetime,
                    end_value=entry_price,
                    line_color='#2196F3',  # 蓝色
                    style='solid',
                    width=4
                )
            except Exception as e:
                print(f"⚠️ 入场价格线段绘制失败: {e}")
            
            # 2. 止损价格线段（红色虚线）
            try:
                self.chart.trend_line(
                    start_time=datetime_obj,
                    start_value=stop_loss_price,
                    end_time=segment_end_datetime,
                    end_value=stop_loss_price,
                    line_color='#F44336',  # 红色
                    style='dashed',
                    width=3
                )
            except Exception as e:
                print(f"⚠️ 止损价格线段绘制失败: {e}")
            
            # 3. 止盈价格线段（绿色虚线）
            try:
                self.chart.trend_line(
                    start_time=datetime_obj,
                    start_value=target_price,
                    end_time=segment_end_datetime,
                    end_value=target_price,
                    line_color='#4CAF50',  # 绿色
                    style='dashed',
                    width=3
                )
            except Exception as e:
                print(f"⚠️ 止盈价格线段绘制失败: {e}")
            
            # 4. 在信号点添加主要标注（入场点）
            direction_text = "📈 看涨" if is_bullish else "📉 看跌"
            main_text = f"{direction_text}\n入场: {entry_price:.5f}"
            
            self.chart.marker(
                time=datetime_obj,
                position='below' if is_bullish else 'above',
                color='blue',
                shape='arrow_up' if is_bullish else 'arrow_down',
                text=main_text
            )
            
            # 5. 添加风险收益比信息（稍微偏右）
            if array_index + 2 < len(self.current_data):
                info_datetime = self.current_data[array_index + 2]['time']
                reward_points = risk_amount * 2
                rr_text = f"💰 风险: {risk_amount:.1f}点\n💎 收益: {reward_points:.1f}点\n⚖️ 盈亏比: 1:2.0"
                
                self.chart.marker(
                    time=info_datetime,
                    position='above' if is_bullish else 'below',
                    color='purple',
                    shape='square',
                    text=rr_text
                )
            
            # 6. 添加止损价格标注（再右边一点）
            if array_index + 4 < len(self.current_data):
                sl_datetime = self.current_data[array_index + 4]['time']
                sl_text = f"🛑 止损\n{stop_loss_price:.5f}"
                
                self.chart.marker(
                    time=sl_datetime,
                    position='above' if not is_bullish else 'below',
                    color='red',
                    shape='triangle_down' if is_bullish else 'triangle_up',
                    text=sl_text
                )
            
            # 7. 添加止盈价格标注（最右边）
            if array_index + 6 < len(self.current_data):
                tp_datetime = self.current_data[array_index + 6]['time']
                tp_text = f"🎯 止盈\n{target_price:.5f}"
                
                self.chart.marker(
                    time=tp_datetime,
                    position='below' if not is_bullish else 'above',
                    color='green',
                    shape='triangle_up' if is_bullish else 'triangle_down',
                    text=tp_text
                )
            
            # Box绘制完成，输出交由上层方法处理
            
        except Exception as e:
            print(f"⚠️ 添加风险收益Box失败: {e}")
            import traceback
            traceback.print_exc()
            
            # 降级显示：只显示标注，不显示任何线条
            print(f"⚠️ 线段绘制失败，降级为纯标注模式")
    
    def _add_legacy_annotations(self, signal_bars: list, signal_bars_info: list) -> None:
        """
        添加旧版本兼容的信号标注
        
        Args:
            signal_bars: 信号K线索引列表
            signal_bars_info: 信号详细信息列表
        """
        signal_info_map = {info['index']: info for info in signal_bars_info}
        
        for bar_index in signal_bars:
            array_index = bar_index - 1 if bar_index > 0 else bar_index
            
            if 0 <= array_index < len(self.current_data):
                datetime_obj = self.current_data[array_index]['time']
                
                # 获取信号K线的详细信息
                signal_info = signal_info_map.get(bar_index, {})
                signal_description = signal_info.get('description', f'信号K{bar_index}')
                signal_pattern = signal_info.get('pattern', '').lower()
                
                # 根据形态特征判断看涨看跌倾向
                is_bullish_signal = self._is_bullish_pattern(signal_pattern, signal_description.lower())
                
                if is_bullish_signal:
                    marker_color = 'green'
                    marker_shape = 'arrow_up'
                    position = 'below'
                else:
                    marker_color = 'red'
                    marker_shape = 'arrow_down'
                    position = 'above'
                
                self.chart.marker(
                    time=datetime_obj,
                    position=position,
                    color=marker_color,
                    shape=marker_shape,
                    text=signal_description
                )
        
        print(f"✅ 已添加传统模式标注 (信号K线:{len(signal_bars)}个)")
    
    def _find_trade_result(self, signal: dict, datetime_obj, backtest_stats=None) -> str:
        """
        实时计算交易结果（而不是查询历史）
        
        Args:
            signal: 信号字典
            datetime_obj: 信号时间
            backtest_stats: PA回测统计系统（保留参数兼容性）
            
        Returns:
            str: 交易结果 ('target', 'stop_loss', 'time_limit', 'pending')
        """
        try:
            # 获取信号参数
            signal_index = signal.get('index', 0)
            entry_price = signal['entry_price']
            stop_loss_price = signal['stop_loss_price']
            is_bullish = signal['is_bullish']
            
            # 计算目标价格（2:1盈亏比）
            risk_pips = abs(entry_price - stop_loss_price)
            if is_bullish:
                target_price = entry_price + risk_pips * 2.0
            else:
                target_price = entry_price - risk_pips * 2.0
            
            # 从信号K线的下一根开始遍历
            start_index = signal_index  # 注意：signal['index']已经是基于1的索引
            max_bars_to_check = 50  # 最多检查50根K线（约12.5小时）
            
            # 确保有足够的数据
            if not self.current_data or start_index >= len(self.current_data):
                return 'pending'
            
            # 遍历后续K线，判断先触及止盈还是止损
            for i in range(start_index, min(start_index + max_bars_to_check, len(self.current_data))):
                bar = self.current_data[i]
                high = bar['high']
                low = bar['low']
                
                if is_bullish:
                    # 看涨交易：检查是否触及止损（低于止损价）或止盈（高于目标价）
                    if low <= stop_loss_price:
                        return 'stop_loss'  # 先触及止损
                    if high >= target_price:
                        return 'target'  # 先触及止盈
                else:
                    # 看跌交易：检查是否触及止损（高于止损价）或止盈（低于目标价）
                    if high >= stop_loss_price:
                        return 'stop_loss'  # 先触及止损
                    if low <= target_price:
                        return 'target'  # 先触及止盈
            
            # 在检查范围内都没有触及止盈或止损
            # 如果已经检查了足够多的K线，认为是超时
            if start_index + max_bars_to_check <= len(self.current_data):
                return 'time_limit'
            else:
                # 数据不足，无法判断
                return 'pending'
                
        except Exception as e:
            print(f"⚠️ 计算交易结果失败: {e}")
            import traceback
            traceback.print_exc()
            return 'pending'
    
    def update_data(self, chart_data: pd.DataFrame) -> None:
        """
        更新图表数据（用于快速刷新）
        
        Args:
            chart_data: 新的图表数据
        """
        if not self.candlestick_series:
            raise Exception("请先创建图表")
        
        # 直接更新数据，无需重建
        self.candlestick_series.update(chart_data)
        self.current_data = []
        for _, row in chart_data.iterrows():
            self.current_data.append({
                'time': row['time'],
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        print(f"✅ 图表数据已更新 ({len(chart_data)} 根K线)")
    
    def show_chart(self, block: bool = True) -> None:
        """
        显示图表
        
        Args:
            block: 是否阻塞显示
        """
        if not self.chart:
            print("❌ 请先创建图表")
            return
        
        try:
            self.chart.show(block=block)
            print("✅ 图表已显示")
            
        except Exception as e:
            print(f"❌ 显示图表失败: {e}")
    
    def _is_bullish_pattern(self, pattern: str, description: str) -> bool:
        """
        判断吞没模式是否为看涨信号
        
        Args:
            pattern: 形态名称
            description: 形态描述
            
        Returns:
            bool: True为看涨，False为看跌
        """
        # 看涨吞没模式
        if '看涨吞没' in pattern or '看涨吞没' in description:
            return True
        
        # 看跌吞没模式
        if '看跌吞没' in pattern or '看跌吞没' in description:
            return False
        
        # 默认为看跌
        return False


def test_pa_chart_display():
    """测试PA图表显示器功能"""
    print("🧪 测试PA图表显示器")
    print("=" * 50)
    
    try:
        # 创建测试数据
        test_data = []
        base_price = 1.0800
        for i in range(50):
            price_change = (i % 10 - 5) * 0.0001
            open_price = base_price + price_change
            high_price = open_price + 0.0005
            low_price = open_price - 0.0005
            close_price = open_price + (i % 3 - 1) * 0.0002
            
            test_data.append({
                'time': 1640995200 + i * 900,  # 15分钟间隔
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price
            })
        
        # 创建图表显示器
        chart_display = PA_ChartDisplay()
        chart = chart_display.create_chart("价格行为测试图表")
        
        # 加载数据
        chart_display.load_data(test_data)
        
        # 测试添加标注
        mock_analysis = {
            'pattern_type': 'wedge_top',
            'confidence': 0.85,
            'key_levels': [1.0820, 1.0800, 1.0780],
            'signal_bars': [45, 47, 49],
            'trade_signal': 'sell',
            'description': '看跌楔形完成，建议做空'
        }
        
        chart_display.add_pattern_annotation(mock_analysis)
        
        # 添加水平线
        chart_display.add_horizontal_line(1.0800, 'red', '关键阻力')
        
        # 显示标注摘要
        print(chart_display.get_annotation_summary())
        
        # 显示图表（非阻塞模式）
        print("📊 图表创建成功，可以调用 show_chart() 显示")
        
        print("✅ PA图表显示器测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_pa_chart_display()