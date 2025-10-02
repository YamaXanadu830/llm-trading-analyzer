#!/usr/bin/env python3
"""
50%回撤入场策略测试脚本
用于验证新增的回撤入场功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from pa.pa_kline_analyzer import PA_KLineAnalyzer, PAAnalysisConfig
from pa.pa_data_reader import PA_DataReader
import pandas as pd

def test_retracement_entry():
    """测试50%回撤入场功能"""
    print("🎯 测试50%回撤入场功能")
    print("=" * 60)
    
    try:
        # 创建启用回撤入场的配置
        config = PAAnalysisConfig(
            # 基础参数
            k_line_value=15,
            risk_reward_ratio=2.0,
            
            # 禁用其他过滤器以便测试回撤功能
            wick_ratio=0.0,  # 禁用影线过滤
            enable_atr_filter=False,  # 禁用ATR过滤
            
            # 启用回撤入场参数
            enable_retracement_entry=True,
            retracement_target=0.50,              # 50%回撤
            retracement_tolerance=0.05,           # ±5%容差
            max_retracement_wait_bars=10,         # 最大等待10根K线
            retracement_invalidation=0.786,       # 78.6%失效水平
            enable_retracement_stats=True         # 启用统计
        )
        
        print(f"📊 配置参数:")
        print(f"   回撤目标: {config.retracement_target:.0%}")
        print(f"   容差范围: ±{config.retracement_tolerance:.0%}")
        print(f"   最大等待: {config.max_retracement_wait_bars}根K线")
        print(f"   失效水平: {config.retracement_invalidation:.1%}")
        
        # 获取测试数据
        reader = PA_DataReader()
        recent_data = reader.get_recent_data(count=100)  # 获取更多数据以便测试
        
        if recent_data.empty:
            print("❌ 无法获取测试数据")
            return
            
        print(f"\n📈 使用数据范围:")
        print(f"   数据量: {len(recent_data)}根K线")
        print(f"   时间范围: {recent_data['datetime'].iloc[0]} 至 {recent_data['datetime'].iloc[-1]}")
        print(f"   价格范围: {recent_data['low'].min():.5f} - {recent_data['high'].max():.5f}")
        
        # 创建分析器并分析
        analyzer = PA_KLineAnalyzer(config=config)
        result = analyzer.analyze_kline_data(recent_data)
        
        # 检查回撤信号
        engulfing_retracement_signals = result.get('engulfing_retracement_signals', [])
        
        print(f"\n🔍 回撤分析结果:")
        if engulfing_retracement_signals:
            print(f"   检测到 {len(engulfing_retracement_signals)} 个回撤入场信号:")
            
            for i, signal in enumerate(engulfing_retracement_signals[:3], 1):  # 显示前3个信号
                engulfing_info = signal['engulfing_info']
                entry_opportunity = signal['entry_opportunity']
                retracement_levels = signal['retracement_levels']
                
                print(f"\n   信号 {i}: K{signal['engulfing_index']:03d} - {engulfing_info['pattern_type']}")
                print(f"   时间: {signal['signal_datetime']}")
                print(f"   强度: {engulfing_info['strength']} (吞没比例: {engulfing_info['engulf_ratio']:.2f})")
                
                # 入场方式对比
                immediate = signal['entry_methods']['immediate_entry']
                retracement = signal['entry_methods']['retracement_entry'] 
                
                print(f"   立即入场: {immediate['price']:.5f} ({immediate['type']})")
                print(f"   回撤入场: {retracement['price']:.5f} ({retracement['type']}) - {retracement['status']}")
                
                # 如果有回撤机会，显示详细信息
                if entry_opportunity['status'] == 'entry_opportunity':
                    print(f"   ✅ 回撤机会发现:")
                    print(f"      实际回撤价位: {entry_opportunity['actual_entry_price']:.5f}")
                    print(f"      回撤百分比: {entry_opportunity['actual_retracement_percentage']:.1%}")
                    print(f"      等待时间: {entry_opportunity['bars_waited']}根K线")
                    
                    # 计算价位改善
                    price_improvement = abs(immediate['price'] - retracement['price']) / 0.0001  # 转换为点数
                    print(f"      价位改善: {price_improvement:.1f}点")
                elif entry_opportunity['status'] == 'invalidated':
                    print(f"   ❌ 回撤失效: {entry_opportunity['reason']}")
                else:
                    print(f"   ⏳ 等待回撤: {entry_opportunity['reason']}")
                
                print(f"   吞没K线范围: {retracement_levels['engulfing_range_points']:.1f}点")
        else:
            print("   未检测到回撤入场信号")
        
        # 显示汇总统计
        print(f"\n📊 测试结果汇总:")
        print(f"   总K线数: {result['total_klines']}")
        print(f"   阳线: {result['bullish_count']}根, 阴线: {result['bearish_count']}根")
        print(f"   传统PA信号: {len(result['trading_signals'])}个")
        print(f"   回撤入场信号: {len(engulfing_retracement_signals)}个")
        
        # 如果有吞没信号，计算回撤成功率
        if engulfing_retracement_signals:
            entry_opportunities = sum(1 for s in engulfing_retracement_signals 
                                    if s['entry_opportunity']['status'] == 'entry_opportunity')
            invalidations = sum(1 for s in engulfing_retracement_signals 
                              if s['entry_opportunity']['status'] == 'invalidated')
            waiting = len(engulfing_retracement_signals) - entry_opportunities - invalidations
            
            print(f"\n🎯 回撤入场效果评估:")
            print(f"   回撤机会: {entry_opportunities}个 ({entry_opportunities/len(engulfing_retracement_signals)*100:.1f}%)")
            print(f"   回撤失效: {invalidations}个 ({invalidations/len(engulfing_retracement_signals)*100:.1f}%)")
            print(f"   等待中: {waiting}个 ({waiting/len(engulfing_retracement_signals)*100:.1f}%)")
            
            if entry_opportunities > 0:
                print(f"   💡 建议: 回撤入场策略在当前数据中表现良好，建议启用")
            else:
                print(f"   ⚠️  建议: 回撤机会较少，可考虑调整参数或结合立即入场")
        
        print("\n✅ 50%回撤入场功能测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_retracement_parameters():
    """测试不同回撤参数的效果"""
    print("\n🔧 测试不同回撤参数效果")
    print("=" * 60)
    
    # 获取数据
    reader = PA_DataReader()
    test_data = reader.get_recent_data(count=80)
    
    if test_data.empty:
        print("❌ 无数据用于参数测试")
        return
    
    # 测试不同的回撤目标
    retracement_targets = [0.38, 0.50, 0.618]  # 38.2%, 50%, 61.8%
    
    print(f"📊 参数对比测试 (数据量: {len(test_data)}根K线):")
    print(f"{'回撤目标':<10} {'入场机会':<8} {'失效率':<8} {'等待率':<8}")
    print("-" * 40)
    
    for target in retracement_targets:
        config = PAAnalysisConfig(
            enable_retracement_entry=True,
            retracement_target=target,
            retracement_tolerance=0.05,
            max_retracement_wait_bars=8,
            enable_retracement_stats=False,  # 避免重复统计
            # 禁用其他过滤器
            wick_ratio=0.0,
            enable_atr_filter=False
        )
        
        analyzer = PA_KLineAnalyzer(config=config)
        result = analyzer.analyze_kline_data(test_data)
        
        signals = result.get('engulfing_retracement_signals', [])
        if signals:
            opportunities = sum(1 for s in signals if s['entry_opportunity']['status'] == 'entry_opportunity')
            invalidations = sum(1 for s in signals if s['entry_opportunity']['status'] == 'invalidated')
            waiting = len(signals) - opportunities - invalidations
            
            opp_rate = opportunities / len(signals) * 100
            inv_rate = invalidations / len(signals) * 100
            wait_rate = waiting / len(signals) * 100
            
            print(f"{target:.1%}      {opportunities:>3}/{len(signals):<2}     {inv_rate:>5.1f}%    {wait_rate:>5.1f}%")
        else:
            print(f"{target:.1%}      {'0/0':<8}     {'N/A':<8} {'N/A':<8}")
    
    print(f"\n💡 建议: 50%回撤通常是最佳平衡点，38.2%较激进，61.8%较保守")

if __name__ == "__main__":
    test_retracement_entry()
    test_retracement_parameters()