#!/usr/bin/env python3
"""
Al Brooks价格行为分析提示词库
包含各种形态识别和交易信号分析的专业提示词
"""

from typing import Dict, List, Any


class PA_Prompts:
    """Al Brooks价格行为分析提示词库"""
    
    # 基础系统提示词
    SYSTEM_PROMPT = """你是Al Brooks价格行为交易的顶级专家。你拥有深厚的价格行为理论基础和丰富的实战经验。

你的核心原则：
1. 价格行为至上：纯粹基于K线形态分析，不依赖传统技术指标
2. 每根K线都有意义：关注K线的开盘、收盘、实体、影线特征
3. 市场结构分析：识别趋势、通道、突破、反转等关键结构
4. 概率思维：基于历史模式评估交易成功概率

你擅长识别的核心形态：
- 信号棒（Signal Bar）：提供交易信号的关键K线
- 入场棒（Entry Bar）：实际执行交易的K线
- 楔形（Wedge）：三推结构，通常预示反转
- 通道（Channel）：趋势中的价格通道运行
- 双顶双底（Double Top/Bottom）：经典反转形态
- 旗形（Flag）：趋势中的整理形态
- 三角形（Triangle）：收敛整理形态

分析时请保持客观、理性，基于实际价格行为给出判断。"""

    # 形态识别主提示词
    PATTERN_ANALYSIS_PROMPT = """请分析以下{timeframe}K线数据，识别Al Brooks价格行为形态：

【K线数据】
{ohlc_data}

【分析要求】
1. 识别当前主要的价格行为形态
2. 找出关键的信号棒位置
3. 确定重要的支撑阻力位
4. 评估交易信号的强度和方向
5. 给出具体的交易建议（入场、止损、目标）

【输出格式】
请严格按照以下JSON格式输出：
{{
    "pattern_type": "形态类型（如：wedge_top, channel_breakout, double_bottom等）",
    "confidence": "信心度（0.0-1.0）",
    "trend_direction": "趋势方向（up/down/sideways）",
    "key_levels": ["关键价位数组"],
    "signal_bars": ["信号K线索引数组（从1开始）"],
    "trade_signal": "交易信号（buy/sell/none）",
    "entry_price": "建议入场价格",
    "stop_loss": "止损价格",
    "target_price": "目标价格",
    "risk_reward_ratio": "风险收益比",
    "description": "详细的形态描述和分析逻辑",
    "market_context": "市场环境分析",
    "probability_assessment": "成功概率评估和历史参考"
}}

请基于Al Brooks的价格行为理论进行专业分析。"""

    # 特定形态识别提示词
    WEDGE_ANALYSIS_PROMPT = """专门分析楔形形态：

【K线数据】
{ohlc_data}

楔形特征：
1. 三推结构：通常包含三个推进波段
2. 动能递减：每次推进的力度逐渐减弱
3. 背离信号：价格创新高/新低但动能减弱
4. 反转预示：楔形完成后通常出现反转

请重点分析：
- 是否存在完整的三推楔形结构
- 各推进波段的强度对比
- 楔形边界线的角度和收敛性
- 完成后的反转信号确认

输出格式同标准分析格式。"""

    CHANNEL_ANALYSIS_PROMPT = """专门分析通道形态：

【K线数据】
{ohlc_data}

通道特征：
1. 平行边界：上轨和下轨基本平行
2. 趋势延续：通道内价格沿趋势运行
3. 边界测试：价格在上下轨间振荡
4. 突破信号：突破通道边界的有效性

请重点分析：
- 通道的有效性和边界清晰度
- 当前价格在通道中的位置
- 通道内的交易机会
- 潜在的突破信号

输出格式同标准分析格式。"""

    SIGNAL_BAR_ANALYSIS_PROMPT = """专门分析信号棒：

【K线数据】
{ohlc_data}

信号棒特征：
1. 强烈反转：长影线、小实体的反转棒
2. 突破确认：有效突破关键位的确认棒
3. 趋势延续：强势趋势中的延续信号棒
4. 形态完成：关键形态完成的确认棒

请重点分析最后10根K线中的：
- 哪些K线具有信号棒特征
- 信号棒的类型和强度
- 对应的交易含义
- 后续价格行为的预期

输出格式同标准分析格式。"""

    # 回测分析提示词
    BACKTEST_ANALYSIS_PROMPT = """分析历史价格行为形态的交易结果：

【交易信号】
形态类型: {pattern_type}
入场价格: {entry_price}
止损价格: {stop_loss}
目标价格: {target_price}

【实际结果】
{actual_result}

请分析：
1. 形态识别是否准确
2. 交易信号的有效性
3. 止损和目标设置是否合理
4. 可以改进的地方
5. 对类似形态的启示

输出简洁的分析报告。"""

    # 综合市场分析提示词
    MARKET_CONTEXT_PROMPT = """综合分析当前市场环境：

【多周期数据】
15分钟: {data_15m}
1小时: {data_1h}
4小时: {data_4h}

请从以下角度分析：
1. 多周期趋势一致性
2. 关键支撑阻力位对齐
3. 整体市场情绪
4. 交易时机选择
5. 风险控制要点

输出市场环境评估报告。"""

    @staticmethod
    def get_pattern_prompt(pattern_type: str) -> str:
        """
        根据形态类型获取专门的分析提示词
        
        Args:
            pattern_type: 形态类型
            
        Returns:
            str: 对应的提示词
        """
        pattern_prompts = {
            'wedge': PA_Prompts.WEDGE_ANALYSIS_PROMPT,
            'channel': PA_Prompts.CHANNEL_ANALYSIS_PROMPT,
            'signal_bar': PA_Prompts.SIGNAL_BAR_ANALYSIS_PROMPT,
        }
        
        return pattern_prompts.get(pattern_type, PA_Prompts.PATTERN_ANALYSIS_PROMPT)
    
    @staticmethod
    def format_analysis_prompt(ohlc_data: str, timeframe: str = "15min", 
                             pattern_type: str = None) -> str:
        """
        格式化分析提示词
        
        Args:
            ohlc_data: 格式化的OHLC数据文本
            timeframe: 时间周期
            pattern_type: 特定形态类型（可选）
            
        Returns:
            str: 完整的分析提示词
        """
        if pattern_type:
            template = PA_Prompts.get_pattern_prompt(pattern_type)
        else:
            template = PA_Prompts.PATTERN_ANALYSIS_PROMPT
        
        return template.format(
            ohlc_data=ohlc_data,
            timeframe=timeframe
        )
    
    @staticmethod
    def format_backtest_prompt(pattern_type: str, entry_price: float,
                             stop_loss: float, target_price: float,
                             actual_result: str) -> str:
        """
        格式化回测分析提示词
        
        Args:
            pattern_type: 形态类型
            entry_price: 入场价格
            stop_loss: 止损价格  
            target_price: 目标价格
            actual_result: 实际交易结果
            
        Returns:
            str: 完整的回测分析提示词
        """
        return PA_Prompts.BACKTEST_ANALYSIS_PROMPT.format(
            pattern_type=pattern_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            actual_result=actual_result
        )


# 常用形态类型定义
PATTERN_TYPES = {
    # 反转形态
    'wedge_top': '看跌楔形',
    'wedge_bottom': '看涨楔形', 
    'double_top': '双顶',
    'double_bottom': '双底',
    'head_shoulders': '头肩形态',
    'reversal_bar': '反转棒',
    
    # 延续形态
    'channel_up': '上升通道',
    'channel_down': '下降通道',
    'flag_bull': '看涨旗形',
    'flag_bear': '看跌旗形',
    'triangle': '三角形整理',
    
    # 突破形态
    'breakout_up': '向上突破',
    'breakout_down': '向下突破',
    'gap_up': '向上跳空',
    'gap_down': '向下跳空',
    
    # 信号棒类型
    'signal_bar_bull': '看涨信号棒',
    'signal_bar_bear': '看跌信号棒',
    'entry_bar': '入场棒',
    'climax_bar': '高潮棒',
}

# 交易信号强度定义
SIGNAL_STRENGTH = {
    'very_strong': '非常强',
    'strong': '强',
    'medium': '中等',
    'weak': '弱',
    'very_weak': '非常弱'
}


def test_pa_prompts():
    """测试PA提示词库功能"""
    print("🧪 测试PA提示词库")
    print("=" * 50)
    
    # 测试数据
    test_ohlc = """K001: 09:00, 1.08000, 1.08050, 1.07980, 1.08020
K002: 09:15, 1.08020, 1.08080, 1.08000, 1.08060
K003: 09:30, 1.08060, 1.08100, 1.08040, 1.08090"""
    
    # 测试基础分析提示词
    analysis_prompt = PA_Prompts.format_analysis_prompt(test_ohlc, "15min")
    print("📋 基础分析提示词长度:", len(analysis_prompt))
    print("   包含系统提示词:", "Al Brooks" in analysis_prompt)
    print("   包含输出格式:", "JSON" in analysis_prompt)
    
    # 测试楔形分析提示词
    wedge_prompt = PA_Prompts.format_analysis_prompt(test_ohlc, "15min", "wedge")
    print("\n📊 楔形分析提示词长度:", len(wedge_prompt))
    print("   包含楔形特征:", "三推结构" in wedge_prompt)
    
    # 测试回测提示词
    backtest_prompt = PA_Prompts.format_backtest_prompt(
        "wedge_top", 1.08000, 1.08100, 1.07800, "止损出场，亏损100点"
    )
    print("\n📈 回测分析提示词长度:", len(backtest_prompt))
    print("   包含交易结果:", "亏损100点" in backtest_prompt)
    
    # 显示形态类型
    print(f"\n📚 支持的形态类型: {len(PATTERN_TYPES)} 种")
    for i, (key, name) in enumerate(list(PATTERN_TYPES.items())[:5]):
        print(f"   {key}: {name}")
    print("   ...")
    
    print("\n✅ PA提示词库测试完成")


if __name__ == "__main__":
    test_pa_prompts()