#!/usr/bin/env python3
"""
PA形态分析器 - 基于LLM的Al Brooks价格行为形态识别
这是整个系统的核心模块，利用LLM理解和分析K线形态
"""

import json
import re
from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime

from .pa_prompts import PA_Prompts, PATTERN_TYPES
from .pa_kline_analyzer import PA_KLineAnalyzer


class PA_PatternAnalyzer:
    """基于LLM的价格行为形态分析器"""
    
    def __init__(self, llm_client=None, model_name: str = "claude"):
        """
        初始化形态分析器
        
        Args:
            llm_client: LLM客户端（暂时使用模拟）
            model_name: 模型名称
        """
        self.llm_client = llm_client
        self.model_name = model_name
        self.analysis_history = []  # 分析历史记录
        
        # 初始化PA策略级别K线分析器 - 阶段2增强配置
        from .pa_kline_analyzer import PAAnalysisConfig
        pa_config = PAAnalysisConfig(
            # 核心参数
            k_line_value=15,
            risk_reward_ratio=2.0,
            
            # 阶段2增强：影线过滤参数
            wick_ratio=0.33,               # 启用影线过滤
            separate_wick_filter=False,    # 使用统一影线过滤模式
            max_upper_wick_ratio=0.4,     # 上影线最大比例（独立模式时生效）
            max_lower_wick_ratio=0.4,     # 下影线最大比例（独立模式时生效）
            
            # 阶段2增强：ATR过滤参数
            enable_atr_filter=True,        # 启用ATR过滤
            atr_period=14,
            atr_multiplier=1.0,
            atr_filter_mode="moderate",    # 中等过滤模式
            
            # 阶段2增强：组合过滤策略
            require_both_filters=False,    # OR组合策略（至少一个过滤器通过）
            min_signal_strength="weak",    # 最小信号强度要求
            
            # 阶段2增强：统计和调试
            enable_filter_stats=True,      # 启用过滤统计
            debug_filter_details=False     # 调试模式关闭
        )
        self.kline_analyzer = PA_KLineAnalyzer(config=pa_config)
        
        # LLM分析参数
        self.max_tokens = 1500
        self.temperature = 0.3  # 较低的温度确保分析一致性
        
        print(f"✅ PA形态分析器初始化完成 (模型: {model_name})")
    
    def analyze_pattern(self, ohlc_data: pd.DataFrame, 
                       timeframe: str = "15min",
                       pattern_type: Optional[str] = None,
                       context: Optional[str] = None) -> Dict[str, Any]:
        """
        分析价格行为形态
        
        Args:
            ohlc_data: OHLC数据DataFrame
            timeframe: 时间周期
            pattern_type: 特定形态类型（可选）
            context: 额外的分析上下文
            
        Returns:
            Dict: 分析结果
        """
        if ohlc_data.empty:
            return self._create_empty_result("无数据可分析")
        
        try:
            # 🚨 新增：真实K线形态分析
            print("🔍 执行真实K线形态分析...")
            kline_analysis = self.kline_analyzer.analyze_kline_data(ohlc_data)
            
            # 格式化数据为LLM可读格式（包含K线特征）
            llm_data = self._format_data_with_kline_features(ohlc_data, kline_analysis)
            
            # 构建分析提示词
            full_prompt = self._build_analysis_prompt(
                llm_data, timeframe, pattern_type, context
            )
            
            # 调用LLM分析
            llm_response = self._call_llm(full_prompt, len(ohlc_data))
            
            # 如果没有LLM响应，跳过形态分析
            if llm_response is None:
                # 直接返回K线分析结果，不做形态识别
                return self._create_kline_only_analysis(kline_analysis, ohlc_data)
            else:
                # 解析分析结果
                analysis_result = self._parse_llm_response(llm_response)
                
                # 🚨 新增：基于真实K线分析增强结果
                analysis_result = self._enhance_with_real_analysis(
                    analysis_result, kline_analysis, ohlc_data, timeframe
                )
            
            # 记录分析历史
            self._record_analysis(analysis_result, ohlc_data, timeframe)
            
            return analysis_result
            
        except Exception as e:
            error_msg = f"形态分析失败: {str(e)}"
            print(f"❌ {error_msg}")
            return self._create_empty_result(error_msg)
    
    def batch_analyze(self, data_windows: List[pd.DataFrame],
                     timeframe: str = "15min",
                     pattern_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        批量分析多个数据窗口
        
        Args:
            data_windows: 数据窗口列表
            timeframe: 时间周期
            pattern_type: 特定形态类型
            
        Returns:
            List[Dict]: 分析结果列表
        """
        print(f"🔄 开始批量分析 {len(data_windows)} 个数据窗口...")
        
        results = []
        for i, window in enumerate(data_windows):
            print(f"   分析进度: {i+1}/{len(data_windows)}")
            
            result = self.analyze_pattern(window, timeframe, pattern_type)
            results.append(result)
            
            # 避免API调用过于频繁
            if i % 10 == 9:
                print(f"   已完成 {i+1} 个窗口分析...")
        
        print(f"✅ 批量分析完成，共 {len(results)} 个结果")
        return results
    
    def _format_data_for_llm(self, df: pd.DataFrame, max_bars: int = 100) -> str:
        """
        将DataFrame格式化为LLM可读的文本格式
        
        Args:
            df: OHLC数据
            max_bars: 最大K线数量
            
        Returns:
            str: 格式化的文本数据
        """
        # 限制数据量，避免提示词过长
        if len(df) > max_bars:
            df = df.tail(max_bars).reset_index(drop=True)
        
        lines = []
        for i, row in df.iterrows():
            time_str = row['datetime'].strftime('%m-%d %H:%M') if 'datetime' in row else f"K{i+1:03d}"
            line = f"{time_str}: O={row['open']:.5f}, H={row['high']:.5f}, L={row['low']:.5f}, C={row['close']:.5f}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _format_data_with_kline_features(self, df: pd.DataFrame, kline_analysis: Dict[str, Any], max_bars: int = 100) -> str:
        """
        将DataFrame和K线特征格式化为LLM可读的文本格式
        
        Args:
            df: OHLC数据
            kline_analysis: K线分析结果
            max_bars: 最大K线数量
            
        Returns:
            str: 格式化的文本数据
        """
        # 限制数据量，避免提示词过长
        if len(df) > max_bars:
            df = df.tail(max_bars).reset_index(drop=True)
            kline_features = kline_analysis['kline_features'][-max_bars:]
        else:
            kline_features = kline_analysis['kline_features']
        
        lines = []
        lines.append("=== K线数据与形态特征分析 ===")
        
        for i, (row, feature) in enumerate(zip(df.iterrows(), kline_features)):
            _, data = row
            time_str = data['datetime'].strftime('%m-%d %H:%M') if 'datetime' in data else f"K{i+1:03d}"
            
            # 基础价格数据
            price_line = f"{time_str}: O={data['open']:.5f}, H={data['high']:.5f}, L={data['low']:.5f}, C={data['close']:.5f}"
            
            # K线特征
            feature_line = f"    类型:{feature.kline_type.value} 强度:{feature.strength.value} "
            feature_line += f"实体:{feature.body_size:.1f}点 上影:{feature.upper_shadow:.1f}点 下影:{feature.lower_shadow:.1f}点"
            
            if feature.is_reversal_signal:
                feature_line += " [反转信号]"
            
            lines.append(price_line)
            lines.append(feature_line)
        
        # 添加组合分析
        combinations = kline_analysis.get('combinations', [])
        if combinations:
            lines.append("\n=== 吞没模式 ===")
            for combo in combinations:
                lines.append(f"K{combo.start_index:03d}-K{combo.end_index:03d}: {combo.pattern_name} ({combo.pattern_type}, 置信度:{combo.confidence:.1%})")
        
        # 添加统计摘要
        lines.append("\n=== 统计摘要 ===")
        lines.append(f"阳线:{kline_analysis['bullish_count']}根, 阴线:{kline_analysis['bearish_count']}根")
        lines.append(f"吞没模式:{len(combinations)}个")
        
        return "\n".join(lines)
    
    def _enhance_with_real_analysis(self, analysis_result: Dict[str, Any], 
                                  kline_analysis: Dict[str, Any], 
                                  ohlc_data: pd.DataFrame, 
                                  timeframe: str) -> Dict[str, Any]:
        """
        基于真实K线分析结果增强分析结果
        
        Args:
            analysis_result: 基础分析结果
            kline_analysis: K线分析结果
            ohlc_data: 原始数据
            timeframe: 时间周期
            
        Returns:
            Dict: 增强后的结果
        """
        # 🚨 升级：使用PA策略信号替代传统吞没模式
        trading_signals = kline_analysis.get('trading_signals', [])
        combinations = kline_analysis.get('combinations', [])
        condition_statistics = kline_analysis.get('condition_statistics', {})
        
        # 将PA策略结果转换为兼容的signal_bars格式
        signal_bars_with_info = []
        
        if trading_signals:
            # 基于PA策略信号生成信号K线信息
            for signal in trading_signals:
                signal_bars_with_info.append({
                    'index': signal['index'],
                    'type': 'pa_strategy_signal',
                    'pattern': signal['trade_condition'].value,
                    'strength': 'strong' if signal['is_combo_condition'] else 'moderate',
                    'description': signal['label_text']
                })
            analysis_result['signal_source'] = 'pa_strategy_signals'
        else:
            # 如果没有PA策略信号，使用最新的几根K线
            total_bars = len(ohlc_data)
            kline_features = kline_analysis.get('kline_features', [])
            
            for i in range(max(0, total_bars-3), total_bars):
                if i < len(kline_features):
                    feature = kline_features[i]
                    signal_bars_with_info.append({
                        'index': feature.index,
                        'type': 'latest',
                        'pattern': feature.kline_type.value,
                        'strength': feature.strength.value,
                        'description': f"{feature.kline_type.value}({feature.strength.value})"
                    })
            analysis_result['signal_source'] = 'latest_bars'
        
        # 去重并排序
        seen_indices = set()
        unique_signals = []
        for signal_info in sorted(signal_bars_with_info, key=lambda x: x['index']):
            if signal_info['index'] not in seen_indices:
                unique_signals.append(signal_info)
                seen_indices.add(signal_info['index'])
        
        # 更新信号信息（兼容旧版本接口）
        analysis_result['signal_bars'] = [s['index'] for s in unique_signals]
        analysis_result['signal_bars_info'] = unique_signals
        
        # 🚨 新增：PA策略专用字段
        analysis_result['trading_signals'] = trading_signals
        analysis_result['condition_statistics'] = condition_statistics
        
        # 添加PA策略分析摘要
        kline_summary = self.kline_analyzer.get_analysis_summary(kline_analysis)
        analysis_result['kline_analysis_summary'] = kline_summary
        
        # 更新描述，包含PA策略分析结果
        if trading_signals:
            signal_types = list(set([s['trade_condition'].value for s in trading_signals]))
            signal_desc = "、".join(signal_types[:3])  # 最多显示3种类型
            analysis_result['description'] = f"PA策略检测到: {signal_desc} 等{len(trading_signals)}个信号。" + analysis_result.get('description', '')
        else:
            analysis_result['description'] = f"PA策略分析: {kline_analysis['bullish_count']}根阳线, {kline_analysis['bearish_count']}根阴线，未检测到交易信号。"
        
        # 更新元数据
        analysis_result['real_kline_analysis'] = {
            'total_analysis': len(kline_analysis['kline_features']),
            'trading_signals_count': len(trading_signals),
            'conditions_triggered': sum(1 for count in condition_statistics.values() if count > 0),
            'latest_kline_type': kline_analysis['latest_kline'].kline_type.value if kline_analysis['latest_kline'] else 'unknown'
        }
        
        # 传统的增强处理
        analysis_result = self._enhance_analysis_result(analysis_result, ohlc_data, timeframe)
        
        return analysis_result
    
    def _build_analysis_prompt(self, llm_data: str, timeframe: str,
                              pattern_type: Optional[str], context: Optional[str]) -> str:
        """
        构建完整的分析提示词
        
        Args:
            llm_data: 格式化的数据
            timeframe: 时间周期
            pattern_type: 形态类型
            context: 额外上下文
            
        Returns:
            str: 完整提示词
        """
        # 基础提示词
        system_prompt = PA_Prompts.SYSTEM_PROMPT
        
        # 分析提示词
        analysis_prompt = PA_Prompts.format_analysis_prompt(
            llm_data, timeframe, pattern_type
        )
        
        # 添加上下文
        if context:
            analysis_prompt += f"\n\n【额外上下文】\n{context}"
        
        return f"{system_prompt}\n\n{analysis_prompt}"
    
    def _call_llm(self, prompt: str, data_length: int = 100) -> str:
        """
        调用LLM进行分析
        
        Args:
            prompt: 完整提示词
            
        Returns:
            str: LLM响应
        """
        if self.llm_client:
            # 真实的LLM调用逻辑
            try:
                response = self.llm_client.generate(
                    prompt=prompt,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )
                return response
            except Exception as e:
                print(f"❌ LLM调用失败: {e}")
                return None
        else:
            print("⚠️ 未配置LLM客户端，跳过形态分析")
            return None
    
    def _create_kline_only_analysis(self, kline_analysis: Dict[str, Any], ohlc_data: pd.DataFrame) -> Dict[str, Any]:
        """直接返回K线分析结果，跳过LLM形态识别"""
        return kline_analysis
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM的JSON响应
        
        Args:
            response: LLM原始响应
            
        Returns:
            Dict: 解析后的结构化结果
        """
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # 验证必要字段
                required_fields = ['pattern_type', 'confidence', 'trade_signal']
                for field in required_fields:
                    if field not in result:
                        result[field] = 'unknown' if field == 'pattern_type' else 0.0 if field == 'confidence' else 'none'
                
                return result
            else:
                raise ValueError("响应中未找到有效的JSON格式")
                
        except Exception as e:
            print(f"❌ 解析LLM响应失败: {e}")
            return self._create_empty_result(f"响应解析失败: {str(e)}")
    
    def _enhance_analysis_result(self, result: Dict[str, Any], 
                               ohlc_data: pd.DataFrame, 
                               timeframe: str) -> Dict[str, Any]:
        """
        增强分析结果，添加额外信息
        
        Args:
            result: 基础分析结果
            ohlc_data: 原始数据
            timeframe: 时间周期
            
        Returns:
            Dict: 增强后的结果
        """
        # 添加元数据
        result['metadata'] = {
            'analysis_time': datetime.now().isoformat(),
            'data_count': len(ohlc_data),
            'timeframe': timeframe,
            'price_range': {
                'high': float(ohlc_data['high'].max()),
                'low': float(ohlc_data['low'].min()),
                'latest_price': float(ohlc_data['close'].iloc[-1])
            }
        }
        
        # 计算技术指标补充
        result['technical_context'] = self._calculate_technical_context(ohlc_data)
        
        # 形态类型中文名称
        if result['pattern_type'] in PATTERN_TYPES:
            result['pattern_name_cn'] = PATTERN_TYPES[result['pattern_type']]
        
        return result
    
    def _calculate_technical_context(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        计算技术指标上下文
        
        Args:
            df: OHLC数据
            
        Returns:
            Dict: 技术指标信息
        """
        try:
            latest_close = df['close'].iloc[-1]
            
            # 简单移动平均
            sma_20 = df['close'].tail(20).mean() if len(df) >= 20 else latest_close
            sma_50 = df['close'].tail(50).mean() if len(df) >= 50 else latest_close
            
            # 价格相对位置
            price_vs_sma20 = 'above' if latest_close > sma_20 else 'below'
            price_vs_sma50 = 'above' if latest_close > sma_50 else 'below'
            
            # 波动性
            price_range = df['high'].max() - df['low'].min()
            volatility = (price_range / df['close'].mean()) * 100
            
            return {
                'sma_20': round(sma_20, 5),
                'sma_50': round(sma_50, 5),
                'price_vs_sma20': price_vs_sma20,
                'price_vs_sma50': price_vs_sma50,
                'volatility_percent': round(volatility, 2),
                'recent_range': round(price_range, 5)
            }
            
        except Exception as e:
            print(f"⚠️ 技术指标计算失败: {e}")
            return {}
    
    def _create_empty_result(self, error_message: str) -> Dict[str, Any]:
        """
        创建空的分析结果
        
        Args:
            error_message: 错误消息
            
        Returns:
            Dict: 空结果
        """
        return {
            'pattern_type': 'none',
            'confidence': 0.0,
            'trend_direction': 'unknown',
            'key_levels': [],
            'signal_bars': [],
            'trade_signal': 'none',
            'entry_price': 0.0,
            'stop_loss': 0.0,
            'target_price': 0.0,
            'risk_reward_ratio': 0.0,
            'description': error_message,
            'market_context': '',
            'probability_assessment': '',
            'error': True,
            'error_message': error_message
        }
    
    def _record_analysis(self, result: Dict[str, Any], 
                        ohlc_data: pd.DataFrame, timeframe: str) -> None:
        """
        记录分析历史
        
        Args:
            result: 分析结果
            ohlc_data: 数据
            timeframe: 时间周期
        """
        history_record = {
            'timestamp': datetime.now().isoformat(),
            'timeframe': timeframe,
            'data_count': len(ohlc_data),
            'pattern_type': result.get('pattern_type'),
            'confidence': result.get('confidence'),
            'trade_signal': result.get('trade_signal')
        }
        
        self.analysis_history.append(history_record)
        
        # 保持历史记录在合理范围内
        if len(self.analysis_history) > 1000:
            self.analysis_history = self.analysis_history[-500:]
    
    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        获取分析历史摘要
        
        Returns:
            Dict: 摘要统计
        """
        if not self.analysis_history:
            return {'total_analyses': 0}
        
        # 统计各种形态出现频率
        pattern_counts = {}
        signal_counts = {}
        
        for record in self.analysis_history:
            pattern = record['pattern_type']
            signal = record['trade_signal']
            
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            signal_counts[signal] = signal_counts.get(signal, 0) + 1
        
        return {
            'total_analyses': len(self.analysis_history),
            'pattern_distribution': pattern_counts,
            'signal_distribution': signal_counts,
            'latest_analysis': self.analysis_history[-1]['timestamp']
        }


def test_pa_pattern_analyzer():
    """测试PA形态分析器功能"""
    print("🧪 测试PA形态分析器")
    print("=" * 50)
    
    try:
        # 创建分析器
        analyzer = PA_PatternAnalyzer()
        
        # 创建测试数据
        test_data = pd.DataFrame({
            'datetime': pd.date_range(start='2024-01-01 09:00', periods=50, freq='15min'),
            'open': [1.08000 + i * 0.0001 for i in range(50)],
            'high': [1.08000 + i * 0.0001 + 0.0005 for i in range(50)],
            'low': [1.08000 + i * 0.0001 - 0.0005 for i in range(50)],
            'close': [1.08000 + i * 0.0001 + (i % 3 - 1) * 0.0002 for i in range(50)]
        })
        
        # 测试单次分析
        print("\n📊 测试单次形态分析:")
        result = analyzer.analyze_pattern(test_data, "15min")
        
        print(f"   形态类型: {result['pattern_type']}")
        print(f"   信心度: {result['confidence']}")
        print(f"   交易信号: {result['trade_signal']}")
        print(f"   描述: {result['description'][:100]}...")
        
        # 测试格式化功能
        print("\n🔤 测试数据格式化:")
        formatted = analyzer._format_data_for_llm(test_data.head(5))
        print(f"   格式化长度: {len(formatted)} 字符")
        print(f"   首行: {formatted.split()[0]}")
        
        # 测试分析摘要
        print("\n📋 测试分析摘要:")
        summary = analyzer.get_analysis_summary()
        print(f"   总分析次数: {summary['total_analyses']}")
        print(f"   形态分布: {summary.get('pattern_distribution', {})}")
        
        print("\n✅ PA形态分析器测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_pa_pattern_analyzer()