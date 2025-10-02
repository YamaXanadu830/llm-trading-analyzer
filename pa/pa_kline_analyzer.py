#!/usr/bin/env python3
"""
K线形态分析器 - 真正基于K线数据的价格行为分析
实现单根K线特征识别和K线组合模式分析
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum


class KLineType(Enum):
    """K线类型枚举"""
    BULLISH = "bullish"           # 阳线
    BEARISH = "bearish"           # 阴线
    DOJI = "doji"                 # 十字星
    HAMMER = "hammer"             # 锤子线
    HANGING_MAN = "hanging_man"   # 上吊线
    SHOOTING_STAR = "shooting_star"  # 流星线
    INVERTED_HAMMER = "inverted_hammer"  # 倒锤线
    SPINNING_TOP = "spinning_top"   # 陀螺线
    MARUBOZU_BULL = "marubozu_bull"  # 光头阳线
    MARUBOZU_BEAR = "marubozu_bear"  # 光脚阴线


class KLineStrength(Enum):
    """K线强度枚举"""
    VERY_STRONG = "very_strong"     # 非常强
    STRONG = "strong"               # 强
    MODERATE = "moderate"           # 中等
    WEAK = "weak"                   # 弱
    VERY_WEAK = "very_weak"         # 非常弱


class BreakthroughType(Enum):
    """突破类型枚举 - 基于PA策略的3种突破条件"""
    CLOSE_BREAKTHROUGH = "close_breakthrough"    # 收盘价突破（条件1）
    OPEN_BREAKTHROUGH = "open_breakthrough"      # 开盘价突破（条件2）
    EXTREME_BREAKTHROUGH = "extreme_breakthrough" # 极值突破（条件3）
    COMBO_BREAKTHROUGH = "combo_breakthrough"    # 组合突破（条件2+3）


class TradeCondition(Enum):
    """交易条件枚举 - 对应PA策略的8种交易条件"""
    BULL_CLOSE_HIGH = "bull_close_high"          # 看涨：收盘>前高（条件0）
    BULL_CLOSE_OPEN = "bull_close_open"          # 看涨：收盘>前开盘（条件1）  
    BULL_HIGH_HIGH = "bull_high_high"            # 看涨：高点>前高点（条件2）
    BULL_COMBO = "bull_combo"                    # 看涨：组合条件（条件3）
    BEAR_CLOSE_LOW = "bear_close_low"            # 看跌：收盘<前低（条件4）
    BEAR_CLOSE_OPEN = "bear_close_open"          # 看跌：收盘<前开盘（条件5）
    BEAR_LOW_LOW = "bear_low_low"                # 看跌：低点<前低点（条件6）
    BEAR_COMBO = "bear_combo"                    # 看跌：组合条件（条件7）


@dataclass
class KLineFeature:
    """单根K线特征"""
    index: int                    # K线索引（1-based）
    datetime: str                 # 时间
    kline_type: KLineType         # K线类型
    strength: KLineStrength       # 强度
    body_size: float              # 实体大小（点数）
    upper_shadow: float           # 上影线长度
    lower_shadow: float           # 下影线长度
    body_ratio: float             # 实体占整体比例
    upper_shadow_ratio: float     # 上影线比例
    lower_shadow_ratio: float     # 下影线比例
    is_bullish: bool              # 是否看涨
    is_reversal_signal: bool      # 是否反转信号
    # 新增OHLC原始数据用于吞没模式判断
    open_price: float             # 开盘价
    high_price: float             # 最高价
    low_price: float              # 最低价
    close_price: float            # 收盘价
    volume_relative: Optional[float] = None  # 相对成交量


@dataclass
class KLineCombination:
    """K线组合特征 - 升级版支持PA策略高级条件"""
    start_index: int              # 组合开始索引
    end_index: int                # 组合结束索引
    pattern_name: str             # 组合名称
    pattern_type: str             # 组合类型（反转/延续）
    confidence: float             # 置信度
    signal_strength: KLineStrength # 信号强度
    description: str              # 形态描述
    # PA策略扩展字段
    trade_condition: TradeCondition    # 对应的交易条件
    breakthrough_type: BreakthroughType # 突破类型
    is_combo_condition: bool           # 是否为组合条件
    entry_price: float                 # 建议入场价格
    stop_loss_price: float             # 建议止损价格
    risk_amount: float                 # 风险金额（点数）


@dataclass  
class PAAnalysisConfig:
    """PA策略分析配置参数 - 阶段2升级版支持灵活过滤"""
    # 核心交易参数
    k_line_value: int = 15              # 最近K线周期（用于极值判断）
    risk_reward_ratio: float = 2.0      # 盈亏比
    
    # 影线过滤参数（阶段2新增）
    wick_ratio: float = 0.33            # 影线占K线比例上限（0表示禁用）
    separate_wick_filter: bool = False   # 是否独立检查上下影线
    max_upper_wick_ratio: float = 0.4   # 上影线最大比例
    max_lower_wick_ratio: float = 0.4   # 下影线最大比例
    
    # ATR过滤参数（阶段2增强）
    enable_atr_filter: bool = False     # 启用ATR过滤
    atr_period: int = 14                # ATR周期
    atr_multiplier: float = 1.0         # ATR倍数
    atr_filter_mode: str = "strict"     # ATR过滤模式：strict(严格)、moderate(中等)、loose(宽松)
    
    # 组合过滤参数（阶段2新增）
    require_both_filters: bool = False   # 是否同时要求影线和ATR过滤都通过
    min_signal_strength: str = "weak"   # 最小信号强度要求：weak、moderate、strong
    
    # 调试和统计参数
    enable_filter_stats: bool = True    # 启用过滤统计
    debug_filter_details: bool = False  # 调试模式：显示详细过滤信息
    
    # 50%回撤入场参数（阶段3新增）
    enable_retracement_entry: bool = True          # 启用回撤入场策略
    retracement_target: float = 0.50              # 目标回撤比例（50%）
    retracement_tolerance: float = 0.05           # 回撤容差范围（±5%）
    max_retracement_wait_bars: int = 10           # 最大等待K线数
    retracement_invalidation: float = 0.786       # 失效回撤水平（78.6%）
    enable_retracement_stats: bool = True         # 启用回撤统计


class PA_KLineAnalyzer:
    """价格行为K线分析器 - 升级版支持PA策略高级条件"""
    
    def __init__(self, pip_size: float = 0.0001, config: Optional[PAAnalysisConfig] = None):
        """
        初始化K线分析器
        
        Args:
            pip_size: 点差大小（EUR/USD默认0.0001）
            config: PA策略分析配置参数
        """
        self.pip_size = pip_size
        self.config = config or PAAnalysisConfig()
        self.analysis_results = []
        
        # 缓存数据，用于周期极值计算
        self.price_data_cache = None
        self.period_highs = None
        self.period_lows = None
        self.atr_values = None
        
        print(f"✅ K线形态分析器初始化完成 (PA策略阶段2模式)")
        print(f"   核心参数: K线周期={self.config.k_line_value}, 盈亏比={self.config.risk_reward_ratio}")
        
        # 影线过滤信息
        if self.config.wick_ratio > 0:
            if self.config.separate_wick_filter:
                print(f"   影线过滤: 独立模式 (上影线≤{self.config.max_upper_wick_ratio:.0%}, 下影线≤{self.config.max_lower_wick_ratio:.0%})")
            else:
                print(f"   影线过滤: 统一模式 (影线≤{self.config.wick_ratio:.0%})")
        else:
            print(f"   影线过滤: 禁用")
            
        # ATR过滤信息
        if self.config.enable_atr_filter:
            print(f"   ATR过滤: {self.config.atr_filter_mode}模式 (周期={self.config.atr_period}, 倍数={self.config.atr_multiplier})")
        else:
            print(f"   ATR过滤: 禁用")
            
        # 组合过滤信息
        filter_combo = "AND组合" if self.config.require_both_filters else "OR组合"
        print(f"   过滤策略: {filter_combo}, 最小信号强度={self.config.min_signal_strength}")
        
        if self.config.enable_filter_stats:
            print(f"   过滤统计: 启用")
            
        # 回撤入场信息
        if self.config.enable_retracement_entry:
            print(f"   回撤入场: 启用 (目标={self.config.retracement_target:.0%}±{self.config.retracement_tolerance:.0%}, 最大等待={self.config.max_retracement_wait_bars}根)")
        else:
            print(f"   回撤入场: 禁用")
            
        # 添加过滤统计字典
        self.filter_stats = {
            'total_signals_before_filter': 0,
            'wick_filter_passed': 0,
            'wick_filter_failed': 0,
            'atr_filter_passed': 0,
            'atr_filter_failed': 0,
            'combined_filter_passed': 0,
            'final_signals': 0
        }
        
        # 回撤统计字典
        self.retracement_stats = {
            'engulfing_patterns_detected': 0,
            'retracement_opportunities_found': 0,
            'retracement_entries_executed': 0,
            'retracement_invalidations': 0,
            'avg_retracement_percentage': 0.0,
            'retracement_success_rate': 0.0
        } if self.config.enable_retracement_entry else {}
    
    def analyze_single_kline(self, row: pd.Series, index: int) -> KLineFeature:
        """
        分析单根K线特征
        
        Args:
            row: K线数据行
            index: K线索引（1-based）
            
        Returns:
            KLineFeature: K线特征对象
        """
        open_price = float(row['open'])
        high_price = float(row['high'])
        low_price = float(row['low'])
        close_price = float(row['close'])
        datetime_str = row['datetime'].strftime('%m-%d %H:%M')
        
        # 基础计算
        total_range = high_price - low_price
        body_size = abs(close_price - open_price)
        upper_shadow = high_price - max(open_price, close_price)
        lower_shadow = min(open_price, close_price) - low_price
        is_bullish = close_price > open_price
        
        # 比例计算
        body_ratio = body_size / total_range if total_range > 0 else 0
        upper_shadow_ratio = upper_shadow / total_range if total_range > 0 else 0
        lower_shadow_ratio = lower_shadow / total_range if total_range > 0 else 0
        
        # K线类型识别
        kline_type = self._identify_kline_type(
            body_ratio, upper_shadow_ratio, lower_shadow_ratio, is_bullish
        )
        
        # 强度评估
        strength = self._evaluate_kline_strength(body_size, total_range, is_bullish)
        
        # 反转信号判断
        is_reversal = self._is_reversal_signal(kline_type, strength)
        
        return KLineFeature(
            index=index,
            datetime=datetime_str,
            kline_type=kline_type,
            strength=strength,
            body_size=body_size / self.pip_size,  # 转换为点数
            upper_shadow=upper_shadow / self.pip_size,
            lower_shadow=lower_shadow / self.pip_size,
            body_ratio=body_ratio,
            upper_shadow_ratio=upper_shadow_ratio,
            lower_shadow_ratio=lower_shadow_ratio,
            is_bullish=is_bullish,
            is_reversal_signal=is_reversal,
            # 保存OHLC原始数据
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price
        )
    
    def _identify_kline_type(self, body_ratio: float, upper_ratio: float, 
                           lower_ratio: float, is_bullish: bool) -> KLineType:
        """识别K线类型"""
        
        # 十字星：实体很小
        if body_ratio <= 0.1:
            return KLineType.DOJI
        
        # 陀螺线：实体小，上下影线都较长
        if body_ratio <= 0.3 and upper_ratio > 0.3 and lower_ratio > 0.3:
            return KLineType.SPINNING_TOP
        
        # 锤子线/上吊线：下影线长，上影线短，实体在上部
        if lower_ratio >= 0.6 and upper_ratio <= 0.1 and body_ratio <= 0.3:
            return KLineType.HAMMER if is_bullish else KLineType.HANGING_MAN
        
        # 流星线/倒锤线：上影线长，下影线短，实体在下部  
        if upper_ratio >= 0.6 and lower_ratio <= 0.1 and body_ratio <= 0.3:
            return KLineType.SHOOTING_STAR if not is_bullish else KLineType.INVERTED_HAMMER
        
        # 光头阳线/光脚阴线：实体占绝大部分
        if body_ratio >= 0.9:
            return KLineType.MARUBOZU_BULL if is_bullish else KLineType.MARUBOZU_BEAR
        
        # 普通阳线/阴线
        return KLineType.BULLISH if is_bullish else KLineType.BEARISH
    
    def _evaluate_kline_strength(self, body_size: float, total_range: float, 
                               is_bullish: bool) -> KLineStrength:
        """评估K线强度"""
        
        body_points = body_size / self.pip_size
        range_points = total_range / self.pip_size
        
        # 基于实体大小评估强度
        if body_points >= 20:
            return KLineStrength.VERY_STRONG
        elif body_points >= 15:
            return KLineStrength.STRONG
        elif body_points >= 10:
            return KLineStrength.MODERATE
        elif body_points >= 5:
            return KLineStrength.WEAK
        else:
            return KLineStrength.VERY_WEAK
    
    def _is_reversal_signal(self, kline_type: KLineType, strength: KLineStrength) -> bool:
        """判断是否为反转信号 - 暂时禁用单根K线反转信号"""
        
        # 不再识别单根K线反转信号，专注于组合形态（吞没模式）
        return False
    
    def analyze_kline_combination(self, kline_features: List[KLineFeature]) -> List[KLineCombination]:
        """
        分析K线组合模式
        
        Args:
            kline_features: K线特征列表
            
        Returns:
            List[KLineCombination]: K线组合列表
        """
        combinations = []
        
        # 分析2-3根K线组合
        for i in range(len(kline_features) - 1):
            # 两根K线组合
            combo2 = self._analyze_two_kline_pattern(kline_features[i:i+2])
            if combo2:
                combinations.append(combo2)
            
            # 三根K线组合
            if i < len(kline_features) - 2:
                combo3 = self._analyze_three_kline_pattern(kline_features[i:i+3])
                if combo3:
                    combinations.append(combo3)
        
        return combinations
    
    def _analyze_two_kline_pattern(self, features: List[KLineFeature]) -> Optional[KLineCombination]:
        """分析两根K线组合 - 专注于吞没模式"""
        
        if len(features) != 2:
            return None
            
        k1, k2 = features[0], features[1]
        
        # 只识别吞没模式
        if self._is_engulfing_pattern(k1, k2):
            pattern_name = "看涨吞没" if k2.is_bullish else "看跌吞没"
            return KLineCombination(
                start_index=k1.index,
                end_index=k2.index,
                pattern_name=pattern_name,
                pattern_type="反转",
                confidence=0.8,
                signal_strength=k2.strength,
                description=f"{k1.datetime}-{k2.datetime}: {pattern_name}模式，{k2.strength.value}信号"
            )
        
        return None
    
    def _analyze_three_kline_pattern(self, features: List[KLineFeature]) -> Optional[KLineCombination]:
        """分析三根K线组合 - 暂时禁用，专注于两根K线吞没模式"""
        
        # 暂时不识别三根K线组合，专注于两根K线的吞没模式
        return None
    
    def _is_engulfing_pattern(self, k1: KLineFeature, k2: KLineFeature) -> bool:
        """
        识别吞没模式 - 按照TA-Lib标准实现（保持兼容性）
        
        看涨吞没: 前阴线 + 后阳线，且后阳线完全吞没前阴线实体
        看跌吞没: 前阳线 + 后阴线，且后阴线完全吞没前阳线实体
        """
        engulfing_info = self._detect_enhanced_engulfing_pattern_from_features(k1, k2)
        return engulfing_info is not None
    
    def _detect_enhanced_engulfing_pattern_from_features(self, k1: KLineFeature, k2: KLineFeature) -> Optional[Dict[str, Any]]:
        """
        增强版吞没模式检测 - 返回详细信息（阶段3新增）
        
        Args:
            k1: 前一根K线特征
            k2: 当前K线特征（吞没K线）
            
        Returns:
            Dict: 吞没模式详细信息，如无吞没则返回None
        """
        # 看涨吞没检查: 前阴后阳
        if not k1.is_bullish and k2.is_bullish:
            # 后阳线开盘价 < 前阴线收盘价，且后阳线收盘价 > 前阴线开盘价
            bullish_engulfing = (k2.open_price < k1.close_price and 
                               k2.close_price > k1.open_price)
            if bullish_engulfing:
                engulf_ratio = k2.body_size / k1.body_size if k1.body_size > 0 else 2.0
                return {
                    'is_bullish': True,
                    'pattern_type': '看涨吞没',
                    'engulf_ratio': engulf_ratio,
                    'strength': 'strong' if engulf_ratio >= 2.0 else 'moderate',
                    'k1_index': k1.index,
                    'k2_index': k2.index,
                    'engulfing_range': k2.high_price - k2.low_price
                }
                
        # 看跌吞没检查: 前阳后阴  
        if k1.is_bullish and not k2.is_bullish:
            # 后阴线开盘价 > 前阳线收盘价，且后阴线收盘价 < 前阳线开盘价
            bearish_engulfing = (k2.open_price > k1.close_price and 
                                k2.close_price < k1.open_price)
            if bearish_engulfing:
                engulf_ratio = k2.body_size / k1.body_size if k1.body_size > 0 else 2.0
                return {
                    'is_bullish': False,
                    'pattern_type': '看跌吞没',
                    'engulf_ratio': engulf_ratio,
                    'strength': 'strong' if engulf_ratio >= 2.0 else 'moderate',
                    'k1_index': k1.index,
                    'k2_index': k2.index,
                    'engulfing_range': k2.high_price - k2.low_price
                }
                
        return None
    
    
    def _is_star_pattern(self, k1: KLineFeature, k2: KLineFeature, k3: KLineFeature) -> bool:
        """识别星型模式 - 暂时禁用"""
        
        # 暂时禁用星型模式识别，专注于吞没模式
        return False
    
    # ==========================================
    # 50%回撤入场策略方法（阶段3新增）
    # ==========================================
    
    def _calculate_engulfing_retracement_levels(self, engulfing_index: int, 
                                              is_bullish: bool) -> Dict[str, float]:
        """
        计算吞没形态的50%回撤入场水平
        
        Args:
            engulfing_index: 吞没K线索引（0-based）
            is_bullish: 是否为看涨吞没
            
        Returns:
            Dict: 包含各种回撤水平的字典
        """
        if self.price_data_cache is None or engulfing_index >= len(self.price_data_cache):
            return {}
            
        df = self.price_data_cache
        engulfing_candle = df.iloc[engulfing_index]
        
        # 获取吞没K线的高低点
        engulfing_high = engulfing_candle['high']
        engulfing_low = engulfing_candle['low']
        engulfing_range = engulfing_high - engulfing_low
        
        if engulfing_range <= 0:
            return {}
        
        if is_bullish:
            # 看涨吞没：从高点向下回撤
            target_level = engulfing_high - (engulfing_range * self.config.retracement_target)
            entry_upper = engulfing_high - (engulfing_range * (self.config.retracement_target - self.config.retracement_tolerance))
            entry_lower = engulfing_high - (engulfing_range * (self.config.retracement_target + self.config.retracement_tolerance))
            invalidation_level = engulfing_high - (engulfing_range * self.config.retracement_invalidation)
        else:
            # 看跌吞没：从低点向上回撤
            target_level = engulfing_low + (engulfing_range * self.config.retracement_target)
            entry_upper = engulfing_low + (engulfing_range * (self.config.retracement_target + self.config.retracement_tolerance))
            entry_lower = engulfing_low + (engulfing_range * (self.config.retracement_target - self.config.retracement_tolerance))
            invalidation_level = engulfing_low + (engulfing_range * self.config.retracement_invalidation)
        
        return {
            'target_retracement': target_level,
            'entry_upper_bound': entry_upper,
            'entry_lower_bound': entry_lower,
            'invalidation_level': invalidation_level,
            'engulfing_high': engulfing_high,
            'engulfing_low': engulfing_low,
            'engulfing_range_points': engulfing_range / self.pip_size
        }
    
    def _check_retracement_entry_opportunity(self, engulfing_index: int, 
                                           retracement_levels: Dict[str, float],
                                           is_bullish: bool) -> Optional[Dict[str, Any]]:
        """
        检测回撤入场机会
        
        Args:
            engulfing_index: 吞没形态K线索引（0-based）
            retracement_levels: 回撤水平信息
            is_bullish: 是否看涨形态
            
        Returns:
            Dict: 入场机会信息，如无机会则返回None
        """
        if not retracement_levels or self.price_data_cache is None:
            return None
            
        df = self.price_data_cache
        max_wait_index = min(engulfing_index + self.config.max_retracement_wait_bars + 1, len(df))
        
        for i in range(engulfing_index + 1, max_wait_index):
            current_candle = df.iloc[i]
            
            if is_bullish:
                # 看涨回撤：检查是否触及50%回撤位
                if (current_candle['low'] <= retracement_levels['entry_upper_bound'] and
                    current_candle['low'] >= retracement_levels['entry_lower_bound']):
                    
                    # 检查是否过度回撤失效
                    if current_candle['low'] < retracement_levels['invalidation_level']:
                        return {'status': 'invalidated', 'reason': 'excessive_retracement'}
                        
                    actual_retracement_pct = (retracement_levels['engulfing_high'] - current_candle['low']) / (retracement_levels['engulfing_high'] - retracement_levels['engulfing_low'])
                    
                    return {
                        'status': 'entry_opportunity',
                        'entry_price': retracement_levels['target_retracement'],
                        'actual_entry_price': current_candle['low'],
                        'entry_candle_index': i + 1,  # 转换为1-based
                        'actual_retracement_percentage': actual_retracement_pct,
                        'bars_waited': i - engulfing_index
                    }
            else:
                # 看跌回撤：检查是否触及50%回撤位
                if (current_candle['high'] >= retracement_levels['entry_lower_bound'] and 
                    current_candle['high'] <= retracement_levels['entry_upper_bound']):
                    
                    # 检查是否过度回撤失效
                    if current_candle['high'] > retracement_levels['invalidation_level']:
                        return {'status': 'invalidated', 'reason': 'excessive_retracement'}
                        
                    actual_retracement_pct = (current_candle['high'] - retracement_levels['engulfing_low']) / (retracement_levels['engulfing_high'] - retracement_levels['engulfing_low'])
                    
                    return {
                        'status': 'entry_opportunity',
                        'entry_price': retracement_levels['target_retracement'],
                        'actual_entry_price': current_candle['high'],
                        'entry_candle_index': i + 1,  # 转换为1-based
                        'actual_retracement_percentage': actual_retracement_pct,
                        'bars_waited': i - engulfing_index
                    }
        
        return {'status': 'waiting', 'reason': 'no_retracement_yet'}
    
    # ==========================================
    # PA策略 高级条件检测方法
    # ==========================================
    
    def _prepare_price_data(self, df: pd.DataFrame) -> None:
        """
        准备价格数据缓存，计算周期极值和ATR
        
        Args:
            df: K线数据DataFrame
        """
        self.price_data_cache = df.copy()
        
        # 计算周期极值（对应PA策略的ta.lowest和ta.highest）
        self.period_lows = df['low'].rolling(window=self.config.k_line_value, min_periods=1).min()
        self.period_highs = df['high'].rolling(window=self.config.k_line_value, min_periods=1).max()
        
        # 计算ATR（用于波动性过滤）
        if self.config.enable_atr_filter:
            # 计算真实波幅 (True Range)
            high_low = df['high'] - df['low']
            high_close_prev = abs(df['high'] - df['close'].shift(1))
            low_close_prev = abs(df['low'] - df['close'].shift(1))
            
            true_range = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
            self.atr_values = true_range.rolling(window=self.config.atr_period, min_periods=1).mean()
        else:
            self.atr_values = None
    
    def _bull_base_condition(self, i: int) -> bool:
        """
        看涨基础条件：前阴线 + 当前阳线 + 低点触及周期最低
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否满足看涨基础条件
        """
        if i < 1 or self.price_data_cache is None:
            return False
            
        df = self.price_data_cache
        
        # 前阴线：open[1] > close[1]
        prev_bearish = df.iloc[i-1]['open'] > df.iloc[i-1]['close']
        
        # 当前阳线：close > open  
        curr_bullish = df.iloc[i]['close'] > df.iloc[i]['open']
        
        # 低点触及周期最低：low[1] == lowest_price or low == lowest_price
        prev_low_at_period_low = abs(df.iloc[i-1]['low'] - self.period_lows.iloc[i-1]) < 1e-6
        curr_low_at_period_low = abs(df.iloc[i]['low'] - self.period_lows.iloc[i]) < 1e-6
        
        return prev_bearish and curr_bullish and (prev_low_at_period_low or curr_low_at_period_low)
    
    def _bear_base_condition(self, i: int) -> bool:
        """
        看跌基础条件：前阳线 + 当前阴线 + 高点触及周期最高
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否满足看跌基础条件
        """
        if i < 1 or self.price_data_cache is None:
            return False
            
        df = self.price_data_cache
        
        # 前阳线：open[1] < close[1]
        prev_bullish = df.iloc[i-1]['open'] < df.iloc[i-1]['close']
        
        # 当前阴线：close < open
        curr_bearish = df.iloc[i]['close'] < df.iloc[i]['open']
        
        # 高点触及周期最高：high[1] == highest_price or high == highest_price
        prev_high_at_period_high = abs(df.iloc[i-1]['high'] - self.period_highs.iloc[i-1]) < 1e-6
        curr_high_at_period_high = abs(df.iloc[i]['high'] - self.period_highs.iloc[i]) < 1e-6
        
        return prev_bullish and curr_bearish and (prev_high_at_period_high or curr_high_at_period_high)
    
    def _check_wick_filter(self, i: int) -> bool:
        """
        检查影线过滤条件 - 阶段2升级版支持独立上下影线控制
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否通过影线过滤
        """
        if self.config.wick_ratio <= 0 or self.price_data_cache is None:
            return True  # 未启用影线过滤
            
        df = self.price_data_cache
        row = df.iloc[i]
        
        # 计算K线各部分长度
        open_price = row['open']
        high_price = row['high'] 
        low_price = row['low']
        close_price = row['close']
        
        current_length = high_price - low_price
        if current_length <= 0:
            return True
            
        # 计算影线长度
        shadow_high = high_price - max(open_price, close_price)
        shadow_low = min(open_price, close_price) - low_price
        
        # 计算影线比例
        upper_wick_ratio = shadow_high / current_length if current_length > 0 else 0
        lower_wick_ratio = shadow_low / current_length if current_length > 0 else 0
        
        # 阶段2增强：独立上下影线过滤
        if self.config.separate_wick_filter:
            valid_upper_wick = upper_wick_ratio <= self.config.max_upper_wick_ratio
            valid_lower_wick = lower_wick_ratio <= self.config.max_lower_wick_ratio
        else:
            # 传统统一过滤
            valid_upper_wick = upper_wick_ratio <= self.config.wick_ratio
            valid_lower_wick = lower_wick_ratio <= self.config.wick_ratio
        
        passed = valid_upper_wick and valid_lower_wick
        
        # 统计更新
        if self.config.enable_filter_stats:
            if passed:
                self.filter_stats['wick_filter_passed'] += 1
            else:
                self.filter_stats['wick_filter_failed'] += 1
        
        # 调试信息
        if self.config.debug_filter_details and not passed:
            print(f"   🚫 影线过滤未通过 K{i+1}: 上影线={upper_wick_ratio:.1%} 下影线={lower_wick_ratio:.1%}")
            
        return passed
    
    def _check_atr_filter(self, i: int) -> bool:
        """
        检查ATR波动性过滤条件 - 阶段2升级版支持多种过滤模式
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否通过ATR过滤
        """
        if not self.config.enable_atr_filter or self.atr_values is None or i < 1:
            return True  # 未启用ATR过滤
            
        df = self.price_data_cache
        
        # 计算当前K线和前一根K线的组合价格区间
        combined_high = max(df.iloc[i]['high'], df.iloc[i-1]['high'])
        combined_low = min(df.iloc[i]['low'], df.iloc[i-1]['low'])
        combined_range = combined_high - combined_low
        
        # 获取ATR值
        atr_value = self.atr_values.iloc[i]
        
        # 阶段2增强：根据过滤模式调整ATR倍数
        effective_multiplier = self.config.atr_multiplier
        
        if self.config.atr_filter_mode == "strict":
            # 严格模式：使用原始倍数
            effective_multiplier = self.config.atr_multiplier
        elif self.config.atr_filter_mode == "moderate":
            # 中等模式：降低倍数，允许更多信号通过
            effective_multiplier = self.config.atr_multiplier * 0.8
        elif self.config.atr_filter_mode == "loose":
            # 宽松模式：进一步降低倍数
            effective_multiplier = self.config.atr_multiplier * 0.6
        
        # 检查组合区间是否超过调整后的ATR倍数阈值
        threshold = atr_value * effective_multiplier
        passed = combined_range > threshold
        
        # 统计更新
        if self.config.enable_filter_stats:
            if passed:
                self.filter_stats['atr_filter_passed'] += 1
            else:
                self.filter_stats['atr_filter_failed'] += 1
        
        # 调试信息
        if self.config.debug_filter_details and not passed:
            print(f"   🚫 ATR过滤未通过 K{i+1}: 组合区间={combined_range*10000:.1f}点 < ATR阈值={threshold*10000:.1f}点 (模式={self.config.atr_filter_mode})")
            
        return passed
    
    def _is_condition1_bull(self, i: int) -> bool:
        """
        看涨条件1：强势突破 - 收盘价突破前高（阶段2升级版支持组合过滤）
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否满足条件1看涨
        """
        if not self._bull_base_condition(i):
            return False
            
        df = self.price_data_cache
        
        # 收盘突破前高：close > high[1]
        base_condition = df.iloc[i]['close'] > df.iloc[i-1]['high']
        
        if not base_condition:
            return False
        
        # 阶段2增强：统计信号数量
        if self.config.enable_filter_stats:
            self.filter_stats['total_signals_before_filter'] += 1
            
        # 阶段2增强：组合过滤策略
        passed = self._apply_combined_filter_strategy(i)
        
        if passed and self.config.enable_filter_stats:
            self.filter_stats['combined_filter_passed'] += 1
            self.filter_stats['final_signals'] += 1
            
        return passed
    
    def _apply_combined_filter_strategy(self, i: int) -> bool:
        """
        应用组合过滤策略 - 阶段2新增方法
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否通过组合过滤
        """
        wick_passed = self._check_wick_filter(i)
        atr_passed = self._check_atr_filter(i)
        
        if self.config.require_both_filters:
            # AND策略：两个过滤器都必须通过
            combined_passed = wick_passed and atr_passed
        else:
            # OR策略：至少一个过滤器通过，或者都没启用
            if self.config.wick_ratio <= 0 and not self.config.enable_atr_filter:
                # 都没启用，直接通过
                combined_passed = True
            elif self.config.wick_ratio <= 0:
                # 只启用ATR过滤
                combined_passed = atr_passed
            elif not self.config.enable_atr_filter:
                # 只启用影线过滤
                combined_passed = wick_passed
            else:
                # 都启用，OR策略
                combined_passed = wick_passed or atr_passed
        
        # 信号强度检查（如果有需要的话，暂时跳过实现）
        # strength_passed = self._check_signal_strength(i)
        
        return combined_passed
    
    def _is_condition1_bear(self, i: int) -> bool:
        """
        看跌条件1：强势突破 - 收盘价跌破前低（阶段2升级版）
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否满足条件1看跌
        """
        if not self._bear_base_condition(i):
            return False
            
        df = self.price_data_cache
        
        # 收盘跌破前低：close < low[1]
        base_condition = df.iloc[i]['close'] < df.iloc[i-1]['low']
        
        if not base_condition:
            return False
        
        # 阶段2增强：统计和过滤
        if self.config.enable_filter_stats:
            self.filter_stats['total_signals_before_filter'] += 1
            
        passed = self._apply_combined_filter_strategy(i)
        
        if passed and self.config.enable_filter_stats:
            self.filter_stats['combined_filter_passed'] += 1
            self.filter_stats['final_signals'] += 1
            
        return passed
    
    def _is_condition2_bull(self, i: int) -> bool:
        """
        看涨条件2：开盘价突破 - 收盘价突破前开盘价（阶段2升级版）
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否满足条件2看涨
        """
        if not self._bull_base_condition(i):
            return False
            
        df = self.price_data_cache
        
        # 收盘突破前开盘：close > open[1]
        base_condition = df.iloc[i]['close'] > df.iloc[i-1]['open']
        
        if not base_condition:
            return False
        
        # 阶段2增强：统计和过滤
        if self.config.enable_filter_stats:
            self.filter_stats['total_signals_before_filter'] += 1
            
        passed = self._apply_combined_filter_strategy(i)
        
        if passed and self.config.enable_filter_stats:
            self.filter_stats['combined_filter_passed'] += 1
            self.filter_stats['final_signals'] += 1
            
        return passed
    
    def _is_condition2_bear(self, i: int) -> bool:
        """
        看跌条件2：开盘价突破 - 收盘价跌破前开盘价（阶段2升级版）
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否满足条件2看跌
        """
        if not self._bear_base_condition(i):
            return False
            
        df = self.price_data_cache
        
        # 收盘跌破前开盘：close < open[1]
        base_condition = df.iloc[i]['close'] < df.iloc[i-1]['open']
        
        if not base_condition:
            return False
        
        # 阶段2增强：统计和过滤
        if self.config.enable_filter_stats:
            self.filter_stats['total_signals_before_filter'] += 1
            
        passed = self._apply_combined_filter_strategy(i)
        
        if passed and self.config.enable_filter_stats:
            self.filter_stats['combined_filter_passed'] += 1
            self.filter_stats['final_signals'] += 1
            
        return passed
    
    def _is_condition3_bull(self, i: int) -> bool:
        """
        看涨条件3：极值突破 - 高点突破前高点（阶段2升级版）
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否满足条件3看涨
        """
        if not self._bull_base_condition(i):
            return False
            
        df = self.price_data_cache
        
        # 高点突破前高点：high > high[1]
        base_condition = df.iloc[i]['high'] > df.iloc[i-1]['high']
        
        if not base_condition:
            return False
        
        # 阶段2增强：统计和过滤
        if self.config.enable_filter_stats:
            self.filter_stats['total_signals_before_filter'] += 1
            
        passed = self._apply_combined_filter_strategy(i)
        
        if passed and self.config.enable_filter_stats:
            self.filter_stats['combined_filter_passed'] += 1
            self.filter_stats['final_signals'] += 1
            
        return passed
    
    def _is_condition3_bear(self, i: int) -> bool:
        """
        看跌条件3：极值突破 - 低点跌破前低点（阶段2升级版）
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            bool: 是否满足条件3看跌
        """
        if not self._bear_base_condition(i):
            return False
            
        df = self.price_data_cache
        
        # 低点跌破前低点：low < low[1]
        base_condition = df.iloc[i]['low'] < df.iloc[i-1]['low']
        
        if not base_condition:
            return False
        
        # 阶段2增强：统计和过滤
        if self.config.enable_filter_stats:
            self.filter_stats['total_signals_before_filter'] += 1
            
        passed = self._apply_combined_filter_strategy(i)
        
        if passed and self.config.enable_filter_stats:
            self.filter_stats['combined_filter_passed'] += 1
            self.filter_stats['final_signals'] += 1
            
        return passed
    
    def analyze_kline_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        分析整个K线数据集 - 使用PA策略高级逻辑
        
        Args:
            df: K线数据DataFrame
            
        Returns:
            Dict: 完整分析结果
        """
        print(f"🔍 开始PA策略级别分析 {len(df)} 根K线数据...")
        
        # 准备价格数据缓存
        self._prepare_price_data(df)
        
        # 分析每根K线的基本特征
        kline_features = []
        for i, (_, row) in enumerate(df.iterrows()):
            feature = self.analyze_single_kline(row, i + 1)
            kline_features.append(feature)
        
        # PA策略 信号检测
        trading_signals = self._detect_trading_signals(df)
        
        # 生成高级K线组合（基于PA策略条件）
        combinations = self._generate_advanced_combinations(df, trading_signals)
        
        # 阶段3新增：检测吞没形态和回撤入场机会
        engulfing_retracement_signals = self._detect_engulfing_retracement_signals(kline_features)
        
        # 统计分析
        bullish_count = sum(1 for f in kline_features if f.is_bullish)
        bearish_count = len(kline_features) - bullish_count
        
        # 统计PA策略信号
        condition_stats = self._calculate_condition_statistics(trading_signals)
        
        print(f"📊 PA策略分析完成:")
        print(f"   阳线: {bullish_count}根, 阴线: {bearish_count}根")
        print(f"   交易信号: {len(trading_signals)}个")
        print(f"   高级组合: {len(combinations)}个")
        for condition_name, count in condition_stats.items():
            if count > 0:
                print(f"   {condition_name}: {count}个")
        
        # 阶段2新增：显示过滤统计
        self.print_filter_statistics()
        
        # 阶段3新增：显示回撤统计
        if self.config.enable_retracement_entry:
            self.print_retracement_statistics()
        
        return {
            'total_klines': len(df),
            'kline_features': kline_features,
            'combinations': combinations,
            'trading_signals': trading_signals,
            'condition_statistics': condition_stats,
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'reversal_signals': [],  # 不再使用旧的反转信号
            'latest_kline': kline_features[-1] if kline_features else None,
            # 阶段3新增：回撤入场信号
            'engulfing_retracement_signals': engulfing_retracement_signals
        }
    
    def _detect_trading_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        检测PA策略级别的交易信号
        
        Args:
            df: K线数据DataFrame
            
        Returns:
            List[Dict]: PA策略信号列表
        """
        signals = []
        
        for i in range(1, len(df)):  # 从第2根K线开始检查
            signal_info = self._check_all_conditions(i)
            if signal_info:
                signals.append(signal_info)
        
        return signals
    
    def _check_all_conditions(self, i: int) -> Optional[Dict[str, Any]]:
        """
        检查所有交易条件并返回最高优先级的信号
        
        Args:
            i: 当前K线索引（0-based）
            
        Returns:
            Dict: 信号信息，如果没有信号则返回None
        """
        df = self.price_data_cache
        
        # 检查所有条件
        condition1_bull = self._is_condition1_bull(i)
        condition2_bull = self._is_condition2_bull(i)
        condition3_bull = self._is_condition3_bull(i)
        condition1_bear = self._is_condition1_bear(i)
        condition2_bear = self._is_condition2_bear(i)
        condition3_bear = self._is_condition3_bear(i)
        
        # 按照PA策略的优先级逻辑选择显示的条件
        condition_index = -1
        trade_condition = None
        breakthrough_type = None
        is_combo = False
        
        # 组合条件优先级最高
        if condition2_bull and condition3_bull:
            condition_index = 3
            trade_condition = TradeCondition.BULL_COMBO
            breakthrough_type = BreakthroughType.COMBO_BREAKTHROUGH
            is_combo = True
        elif condition2_bear and condition3_bear:
            condition_index = 7
            trade_condition = TradeCondition.BEAR_COMBO
            breakthrough_type = BreakthroughType.COMBO_BREAKTHROUGH
            is_combo = True
        elif condition1_bull:
            condition_index = 0
            trade_condition = TradeCondition.BULL_CLOSE_HIGH
            breakthrough_type = BreakthroughType.CLOSE_BREAKTHROUGH
        elif condition2_bull:
            condition_index = 1
            trade_condition = TradeCondition.BULL_CLOSE_OPEN
            breakthrough_type = BreakthroughType.OPEN_BREAKTHROUGH
        elif condition3_bull:
            condition_index = 2
            trade_condition = TradeCondition.BULL_HIGH_HIGH
            breakthrough_type = BreakthroughType.EXTREME_BREAKTHROUGH
        elif condition1_bear:
            condition_index = 4
            trade_condition = TradeCondition.BEAR_CLOSE_LOW
            breakthrough_type = BreakthroughType.CLOSE_BREAKTHROUGH
        elif condition2_bear:
            condition_index = 5
            trade_condition = TradeCondition.BEAR_CLOSE_OPEN
            breakthrough_type = BreakthroughType.OPEN_BREAKTHROUGH
        elif condition3_bear:
            condition_index = 6
            trade_condition = TradeCondition.BEAR_LOW_LOW
            breakthrough_type = BreakthroughType.EXTREME_BREAKTHROUGH
        
        if condition_index < 0:
            return None
            
        # 构建信号描述
        label_parts = []
        if condition1_bull or condition1_bear:
            label_parts.append('收盘>前高' if condition1_bull else '收盘<前低')
        if condition2_bull or condition2_bear:
            label_parts.append('收盘>前开盘' if condition2_bull else '收盘<前开盘')
        if condition3_bull or condition3_bear:
            label_parts.append('高点>前高点' if condition3_bull else '低点<前低点')
        
        label_text = '+'.join(label_parts)
        
        # 计算交易参数
        is_bullish = condition_index <= 3
        entry_price = df.iloc[i]['close']
        stop_loss = min(df.iloc[i]['low'], df.iloc[i-1]['low']) if is_bullish else max(df.iloc[i]['high'], df.iloc[i-1]['high'])
        risk = abs(entry_price - stop_loss)
        
        return {
            'index': i + 1,  # 转换为1-based索引
            'condition_index': condition_index,
            'trade_condition': trade_condition,
            'breakthrough_type': breakthrough_type,
            'is_combo_condition': is_combo,
            'is_bullish': is_bullish,
            'label_text': label_text,
            'entry_price': entry_price,
            'stop_loss_price': stop_loss,
            'risk_amount': risk / self.pip_size,  # 转换为点数
            'datetime': df.iloc[i]['datetime'] if 'datetime' in df.columns else f'K{i+1:03d}',
            'conditions_satisfied': {
                'condition1_bull': condition1_bull,
                'condition2_bull': condition2_bull,
                'condition3_bull': condition3_bull,
                'condition1_bear': condition1_bear,
                'condition2_bear': condition2_bear,
                'condition3_bear': condition3_bear,
            }
        }
    
    def _generate_advanced_combinations(self, df: pd.DataFrame, trading_signals: List[Dict[str, Any]]) -> List[KLineCombination]:
        """
        基于PA策略信号生成高级K线组合
        
        Args:
            df: K线数据DataFrame
            trading_signals: PA策略信号列表
            
        Returns:
            List[KLineCombination]: 高级组合列表
        """
        combinations = []
        
        for signal in trading_signals:
            index = signal['index']
            trade_condition = signal['trade_condition']
            breakthrough_type = signal['breakthrough_type']
            is_bullish = signal['is_bullish']
            
            # 创建高级K线组合
            combination = KLineCombination(
                start_index=max(1, index - 1),  # 前一根K线作为起始
                end_index=index,
                pattern_name=signal['label_text'],
                pattern_type="反转",
                confidence=0.8 if signal['is_combo_condition'] else 0.7,
                signal_strength=KLineStrength.STRONG if signal['is_combo_condition'] else KLineStrength.MODERATE,
                description=f"{signal['datetime']}: {signal['label_text']} ({trade_condition.value})",
                trade_condition=trade_condition,
                breakthrough_type=breakthrough_type,
                is_combo_condition=signal['is_combo_condition'],
                entry_price=signal['entry_price'],
                stop_loss_price=signal['stop_loss_price'],
                risk_amount=signal['risk_amount']
            )
            
            combinations.append(combination)
        
        return combinations
    
    def _calculate_condition_statistics(self, trading_signals: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        计算各种交易条件的统计信息
        
        Args:
            trading_signals: PA策略信号列表
            
        Returns:
            Dict[str, int]: 条件统计字典
        """
        stats = {
            '看涨收盘>前高': 0,
            '看涨收盘>前开盘': 0, 
            '看涨高点>前高点': 0,
            '看涨组合条件': 0,
            '看跌收盘<前低': 0,
            '看跌收盘<前开盘': 0,
            '看跌低点<前低点': 0,
            '看跌组合条件': 0
        }
        
        condition_map = {
            TradeCondition.BULL_CLOSE_HIGH: '看涨收盘>前高',
            TradeCondition.BULL_CLOSE_OPEN: '看涨收盘>前开盘',
            TradeCondition.BULL_HIGH_HIGH: '看涨高点>前高点',
            TradeCondition.BULL_COMBO: '看涨组合条件',
            TradeCondition.BEAR_CLOSE_LOW: '看跌收盘<前低',
            TradeCondition.BEAR_CLOSE_OPEN: '看跌收盘<前开盘',
            TradeCondition.BEAR_LOW_LOW: '看跌低点<前低点',
            TradeCondition.BEAR_COMBO: '看跌组合条件'
        }
        
        for signal in trading_signals:
            condition_name = condition_map.get(signal['trade_condition'])
            if condition_name:
                stats[condition_name] += 1
        
        return stats
    
    def get_filter_statistics_summary(self) -> Dict[str, Any]:
        """
        获取过滤统计摘要 - 阶段2新增方法
        
        Returns:
            Dict: 过滤统计摘要
        """
        if not self.config.enable_filter_stats:
            return {}
            
        stats = self.filter_stats.copy()
        
        # 计算通过率
        if stats['total_signals_before_filter'] > 0:
            stats['wick_pass_rate'] = stats['wick_filter_passed'] / (stats['wick_filter_passed'] + stats['wick_filter_failed']) * 100 if (stats['wick_filter_passed'] + stats['wick_filter_failed']) > 0 else 0
            stats['atr_pass_rate'] = stats['atr_filter_passed'] / (stats['atr_filter_passed'] + stats['atr_filter_failed']) * 100 if (stats['atr_filter_passed'] + stats['atr_filter_failed']) > 0 else 0
            stats['overall_pass_rate'] = stats['final_signals'] / stats['total_signals_before_filter'] * 100
        else:
            stats['wick_pass_rate'] = 0
            stats['atr_pass_rate'] = 0 
            stats['overall_pass_rate'] = 0
            
        return stats
    
    def print_filter_statistics(self) -> None:
        """
        打印过滤统计信息 - 阶段2新增方法
        """
        if not self.config.enable_filter_stats:
            return
            
        stats = self.get_filter_statistics_summary()
        
        print(f"\n📊 阶段2过滤统计:")
        print(f"   初始信号: {stats['total_signals_before_filter']}个")
        
        if self.config.wick_ratio > 0:
            print(f"   影线过滤: 通过{stats['wick_filter_passed']}个, 拒绝{stats['wick_filter_failed']}个 (通过率:{stats['wick_pass_rate']:.1f}%)")
            
        if self.config.enable_atr_filter:
            print(f"   ATR过滤: 通过{stats['atr_filter_passed']}个, 拒绝{stats['atr_filter_failed']}个 (通过率:{stats['atr_pass_rate']:.1f}%)")
            
        print(f"   最终信号: {stats['final_signals']}个 (总通过率:{stats['overall_pass_rate']:.1f}%)")
        
        if stats['total_signals_before_filter'] > 0:
            reduction_rate = (1 - stats['overall_pass_rate']/100) * 100
            print(f"   信号净化率: {reduction_rate:.1f}% (过滤掉{stats['total_signals_before_filter'] - stats['final_signals']}个低质量信号)")
    
    def get_analysis_summary(self, analysis_result: Dict[str, Any]) -> str:
        """获取分析摘要文本 - 升级版支持PA策略结果"""
        
        kline_features = analysis_result['kline_features']
        combinations = analysis_result['combinations']
        trading_signals = analysis_result.get('trading_signals', [])
        condition_stats = analysis_result.get('condition_statistics', {})
        
        lines = []
        lines.append(f"📊 PA策略分析摘要 (共{len(kline_features)}根):")
        
        # 最新K线特征
        if kline_features:
            latest = kline_features[-1]
            lines.append(f"   最新K线: K{latest.index:03d} {latest.datetime}")
            lines.append(f"   类型: {latest.kline_type.value} ({latest.strength.value})")
            lines.append(f"   实体: {latest.body_size:.1f}点, 上影: {latest.upper_shadow:.1f}点, 下影: {latest.lower_shadow:.1f}点")
        
        # PA策略信号统计
        if trading_signals:
            lines.append(f"\n🎯 PA策略信号 ({len(trading_signals)}个):")
            for condition_name, count in condition_stats.items():
                if count > 0:
                    lines.append(f"   {condition_name}: {count}个")
        
        # 高级组合
        if combinations:
            lines.append(f"\n🔗 高级组合 ({len(combinations)}个):")
            for combo in combinations[-3:]:  # 显示最近3个
                risk_info = f"风险{combo.risk_amount:.1f}点" if hasattr(combo, 'risk_amount') else ""
                combo_type = "组合" if combo.is_combo_condition else "单一"
                lines.append(f"   K{combo.start_index:03d}-K{combo.end_index:03d}: {combo.pattern_name} ({combo_type}) {risk_info}")
        
        return "\n".join(lines)
    
    def _detect_engulfing_retracement_signals(self, kline_features: List[KLineFeature]) -> List[Dict[str, Any]]:
        """
        检测吞没形态回撤入场信号（阶段3新增）
        
        Args:
            kline_features: K线特征列表
            
        Returns:
            List[Dict]: 回撤入场信号列表
        """
        if not self.config.enable_retracement_entry or len(kline_features) < 2:
            return []
            
        retracement_signals = []
        
        # 检测每个可能的吞没形态
        for i in range(len(kline_features) - 1):
            k1 = kline_features[i]
            k2 = kline_features[i + 1]
            
            # 检测吞没模式
            engulfing_info = self._detect_enhanced_engulfing_pattern_from_features(k1, k2)
            
            if engulfing_info:
                # 更新统计
                if self.config.enable_retracement_stats:
                    self.retracement_stats['engulfing_patterns_detected'] += 1
                
                # 计算回撤水平
                retracement_levels = self._calculate_engulfing_retracement_levels(
                    i + 1, engulfing_info['is_bullish']  # i+1是吞没K线的0-based索引
                )
                
                if retracement_levels:
                    # 检查回撤入场机会
                    entry_opportunity = self._check_retracement_entry_opportunity(
                        i + 1, retracement_levels, engulfing_info['is_bullish']
                    )
                    
                    if entry_opportunity:
                        # 更新统计
                        if self.config.enable_retracement_stats:
                            if entry_opportunity['status'] == 'entry_opportunity':
                                self.retracement_stats['retracement_opportunities_found'] += 1
                                self.retracement_stats['retracement_entries_executed'] += 1
                            elif entry_opportunity['status'] == 'invalidated':
                                self.retracement_stats['retracement_invalidations'] += 1
                        
                        # 构建信号
                        signal = {
                            'engulfing_index': k2.index,  # 1-based
                            'engulfing_info': engulfing_info,
                            'retracement_levels': retracement_levels,
                            'entry_opportunity': entry_opportunity,
                            'signal_datetime': k2.datetime,
                            'entry_methods': {
                                'immediate_entry': {
                                    'price': k2.close_price,
                                    'type': 'market_order',
                                    'description': f'吞没形态确认后立即入场'
                                },
                                'retracement_entry': {
                                    'price': retracement_levels['target_retracement'],
                                    'type': 'limit_order',
                                    'status': entry_opportunity['status'],
                                    'description': f'50%回撤入场 ({self.config.retracement_target:.0%}±{self.config.retracement_tolerance:.0%})'
                                }
                            }
                        }
                        
                        retracement_signals.append(signal)
        
        return retracement_signals
    
    def print_retracement_statistics(self) -> None:
        """
        打印回撤入场统计信息（阶段3新增）
        """
        if not self.config.enable_retracement_stats or not self.retracement_stats:
            return
            
        stats = self.retracement_stats
        
        print(f"\n🎯 回撤入场统计:")
        print(f"   检测到吞没形态: {stats['engulfing_patterns_detected']}个")
        print(f"   回撤机会发现: {stats['retracement_opportunities_found']}个")
        print(f"   回撤入场执行: {stats['retracement_entries_executed']}个") 
        print(f"   回撤失效: {stats['retracement_invalidations']}个")
        
        if stats['engulfing_patterns_detected'] > 0:
            success_rate = (stats['retracement_entries_executed'] / stats['engulfing_patterns_detected']) * 100
            print(f"   回撤入场成功率: {success_rate:.1f}%")
            
            if stats['retracement_opportunities_found'] > 0:
                opportunity_rate = (stats['retracement_opportunities_found'] / stats['engulfing_patterns_detected']) * 100
                print(f"   回撤机会出现率: {opportunity_rate:.1f}%")


def test_kline_analyzer():
    """测试K线分析器 - PA策略升级版"""
    print("🧪 测试PA策略级别K线分析器")
    print("=" * 60)
    
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        
        from .pa_data_reader import PA_DataReader
        
        # 获取真实数据
        reader = PA_DataReader()
        recent_data = reader.get_recent_data(count=50)  # 增加数据量以便测试
        
        if recent_data.empty:
            print("❌ 无法获取测试数据")
            return
        
        # 创建PA策略配置 - 先用宽松参数测试
        config = PAAnalysisConfig(
            k_line_value=15,
            risk_reward_ratio=2.0,
            wick_ratio=0.0,  # 禁用影线过滤以便测试
            enable_atr_filter=False,  # 禁用ATR过滤以便测试
            atr_period=14,
            atr_multiplier=1.0
        )
        
        # 创建分析器并分析
        print(f"📊 配置参数:")
        print(f"   K线周期: {config.k_line_value}")
        print(f"   盈亏比: {config.risk_reward_ratio}")
        print(f"   影线过滤: {config.wick_ratio}")
        print(f"   ATR过滤: {'启用' if config.enable_atr_filter else '禁用'}")
        
        analyzer = PA_KLineAnalyzer(config=config)
        result = analyzer.analyze_kline_data(recent_data)
        
        # 显示分析摘要
        summary = analyzer.get_analysis_summary(result)
        print(f"\n{summary}")
        
        # 显示PA策略信号详情
        trading_signals = result.get('trading_signals', [])
        if trading_signals:
            print(f"\n🎯 PA策略信号详情:")
            for i, signal in enumerate(trading_signals[:5]):  # 显示前5个信号
                print(f"   信号{i+1}: K{signal['index']:03d} - {signal['label_text']}")
                print(f"        条件索引: {signal['condition_index']} ({signal['trade_condition'].value})")
                print(f"        突破类型: {signal['breakthrough_type'].value}")
                print(f"        入场价: {signal['entry_price']:.5f}, 止损: {signal['stop_loss_price']:.5f}")
                print(f"        风险: {signal['risk_amount']:.1f}点, {'看涨' if signal['is_bullish'] else '看跌'}")
        
        # 显示高级组合详情
        combinations = result.get('combinations', [])
        if combinations:
            print(f"\n🔗 高级组合详情:")
            for i, combo in enumerate(combinations[:3]):  # 显示前3个组合
                combo_type = "组合条件" if combo.is_combo_condition else "单一条件"
                print(f"   组合{i+1}: {combo.pattern_name} ({combo_type})")
                print(f"        索引: K{combo.start_index:03d}-K{combo.end_index:03d}")
                print(f"        置信度: {combo.confidence:.1%}, 强度: {combo.signal_strength.value}")
                print(f"        风险: {combo.risk_amount:.1f}点")
        
        print("\n✅ PA策略K线分析器测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_kline_analyzer()