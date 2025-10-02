#!/usr/bin/env python3
"""
LLM交易分析系统 - 主入口
支持交互式图表分析和数据管理
"""

import sys
import argparse
import time
from pa.pa_chart_session import PA_ChartSession


def interactive_mode(symbol="EUR/USD", timeframe="15min"):
    """
    交互式图表分析模式
    
    Args:
        symbol: 交易品种
        timeframe: 时间周期
    """
    print("="*60)
    print("🎮 LLM交易分析系统 - 交互式模式")
    print("="*60)
    print(f"品种: {symbol} | 周期: {timeframe}")
    print("\n命令列表:")
    print("  show [count]     - 显示图表（默认1000根K线）")
    print("  calc [count] [参数] - 仅计算PA分析（支持过滤参数）")
    print("  more [count]     - 加载更多历史数据")
    print("  support <price>  - 添加支撑线")
    print("  resist <price>   - 添加阻力线")
    print("  range <start> <end> - 加载日期范围")
    print("  analyze          - 执行PA分析")
    print("  clear            - 清除叠加层")
    print("  status           - 查看状态")
    print("  help             - 显示详细帮助")
    print("  quit             - 退出")
    print("="*60)
    
    session = None
    
    while True:
        try:
            command = input("\n> ").strip().lower()
            
            if command == "quit" or command == "exit":
                print("👋 再见！")
                break
            
            elif command == "help":
                print("\n📚 命令说明:")
                print("  show        - 显示K线图表，自动进行PA分析")
                print("  show 500    - 显示指定数量的K线")
                print("  calc        - 仅计算PA分析，不显示图表")
                print("  calc 2000   - 计算指定数量K线的PA分析")
                print("  calc 1000 wick=0.3 - 带影线过滤（≤30%）")
                print("  calc 1000 atr=on   - 启用ATR波动性过滤")
                print("  calc 1000 rr=3.0   - 设置盈亏比为3:1")
                print("  calc 1000 k_line_value=10 - K线周期调整为10根")
                print("  calc 1000 retracement=on - 启用50%回撤入场")
                print("  calc 1000 ret_target=0.618 - 设置61.8%回撤")
                print("  calc 1000 wick=0.2 atr=on mode=strict - 组合过滤")
                print("  more 300    - 在现有基础上加载更多历史")
                print("  support 1.0850 - 在1.0850添加支撑线")
                print("  resist 1.0900  - 在1.0900添加阻力线")
                print("  range 2024-01-01 2024-03-31 - 加载指定日期范围")
                print("  analyze     - 重新执行PA形态分析")
                print("  clear       - 清除所有支撑阻力线")
                print("  status      - 查看当前会话状态")
                print("\n📊 calc过滤参数:")
                print("  wick=0.3    - 影线过滤（0禁用，0.1-0.5常用）")
                print("  atr=on/off  - ATR过滤开关")
                print("  atr_mult=1.5 - ATR倍数（0.5-3.0，自动启用ATR）")
                print("  atr_period=14 - ATR周期（默认14）")
                print("  k_line_value=15 - K线周期（5-30，用于最高最低点计算）")
                print("  rr=2.0      - 盈亏比（1.5-3.0常用）")
                print("  mode=strict/moderate/loose - ATR预设模式")
                print("  both=on     - 要求影线和ATR都通过")
                print("  retracement=on/off - 50%回撤入场开关")
                print("  ret_target=0.50 - 回撤目标（0.382/0.50/0.618常用）")
                print("  ret_tolerance=0.05 - 回撤容差（±5%）")
                print("  ret_wait=10 - 最大等待K线数")
            
            elif command.startswith("show"):
                parts = command.split()
                count = int(parts[1]) if len(parts) > 1 else 1000
                
                if session is None:
                    session = PA_ChartSession(symbol=symbol, timeframe=timeframe)
                
                print(f"📊 显示{count}根K线...")
                session.show(count=count, analyze=True)
            
            elif command.startswith("calc"):
                parts = command.split()
                count = 1000  # 默认值
                config_params = {}
                
                # 简单解析：calc [count] [key=value ...]
                for part in parts[1:]:
                    if '=' in part:
                        key, value = part.split('=', 1)
                        config_params[key] = value
                    elif part.isdigit():
                        count = int(part)
                
                # 直接进行计算，不创建或显示图表
                from pa.pa_data_reader import PA_DataReader
                from pa.pa_kline_analyzer import PA_KLineAnalyzer, PAAnalysisConfig
                
                # 创建配置（只修改用户指定的参数）
                config = PAAnalysisConfig()
                
                # 应用用户参数
                if 'wick' in config_params:
                    config.wick_ratio = float(config_params['wick'])
                if 'atr' in config_params:
                    config.enable_atr_filter = config_params['atr'].lower() == 'on'
                if 'rr' in config_params:
                    config.risk_reward_ratio = float(config_params['rr'])
                if 'mode' in config_params and config_params['mode'] in ['strict', 'moderate', 'loose']:
                    config.atr_filter_mode = config_params['mode']
                if 'atr_mult' in config_params:
                    config.atr_multiplier = float(config_params['atr_mult'])
                    config.enable_atr_filter = True  # 自动启用ATR过滤
                if 'atr_period' in config_params:
                    config.atr_period = int(config_params['atr_period'])
                    config.enable_atr_filter = True  # 自动启用ATR过滤
                if 'k_line_value' in config_params:
                    config.k_line_value = int(config_params['k_line_value'])
                if 'both' in config_params:
                    config.require_both_filters = config_params['both'].lower() == 'on'
                
                # 50%回撤入场参数
                if 'retracement' in config_params:
                    config.enable_retracement_entry = config_params['retracement'].lower() == 'on'
                if 'ret_target' in config_params:
                    config.retracement_target = float(config_params['ret_target'])
                    config.enable_retracement_entry = True  # 自动启用
                if 'ret_tolerance' in config_params:
                    config.retracement_tolerance = float(config_params['ret_tolerance'])
                if 'ret_wait' in config_params:
                    config.max_retracement_wait_bars = int(config_params['ret_wait'])
                
                # 显示配置信息
                print(f"📊 计算{count}根K线的PA分析...")
                config_info = []
                if config.wick_ratio > 0:
                    config_info.append(f"影线≤{config.wick_ratio:.0%}")
                if config.enable_atr_filter:
                    if 'atr_mult' in config_params:
                        config_info.append(f"ATR过滤=开启(倍数={config.atr_multiplier})")
                    else:
                        config_info.append(f"ATR过滤=开启({config.atr_filter_mode})")
                    if config.atr_period != 14:
                        config_info.append(f"ATR周期={config.atr_period}")
                if config.risk_reward_ratio != 2.0:
                    config_info.append(f"盈亏比={config.risk_reward_ratio}")
                if config.k_line_value != 15:
                    config_info.append(f"K线周期={config.k_line_value}")
                if config.require_both_filters:
                    config_info.append("组合过滤=AND")
                
                # 回撤入场配置显示
                if config.enable_retracement_entry:
                    ret_info = f"回撤入场={config.retracement_target:.0%}"
                    if config.retracement_tolerance != 0.05:
                        ret_info += f"±{config.retracement_tolerance:.0%}"
                    if config.max_retracement_wait_bars != 10:
                        ret_info += f"(等待{config.max_retracement_wait_bars}根)"
                    config_info.append(ret_info)
                
                if config_info:
                    print(f"🔧 过滤设置: {', '.join(config_info)}")
                else:
                    print("🔧 过滤设置: 默认（无过滤）")
                
                print("⏳ 正在获取数据...")
                
                # 获取数据
                data_reader = PA_DataReader()
                data = data_reader.get_recent_data(symbol, timeframe, count)
                
                if data.empty:
                    print("❌ 无数据可分析")
                    continue
                
                print(f"✅ 获取 {symbol} {timeframe} 最近 {len(data)} 根K线")
                
                # 执行K线分析
                print("🔍 执行真实K线形态分析...")
                kline_analyzer = PA_KLineAnalyzer(config=config)
                analysis_result = kline_analyzer.analyze_kline_data(data)
                
                # 输出分析结果
                print("🔍 开始PA策略级别分析 {} 根K线数据...".format(len(data)))
                print("📊 PA策略分析完成:")
                
                # 统计信息
                trading_signals = analysis_result.get('trading_signals', [])
                combinations = analysis_result.get('combinations', [])
                
                # 计算阳线和阴线数量
                bullish_count = sum(1 for _, row in data.iterrows() if row['close'] > row['open'])
                bearish_count = len(data) - bullish_count
                print(f"   阳线: {bullish_count}根, 阴线: {bearish_count}根")
                print(f"   交易信号: {len(trading_signals)}个")
                print(f"   高级组合: {len(combinations)}个")
                
                # 阶段3新增：回撤入场信号统计
                retracement_signals = analysis_result.get('engulfing_retracement_signals', [])
                if retracement_signals:
                    entry_opportunities = sum(1 for s in retracement_signals 
                                            if s['entry_opportunity']['status'] == 'entry_opportunity')
                    invalidations = sum(1 for s in retracement_signals 
                                      if s['entry_opportunity']['status'] == 'invalidated')
                    waiting = len(retracement_signals) - entry_opportunities - invalidations
                    
                    print(f"   回撤入场信号: {len(retracement_signals)}个")
                    if entry_opportunities > 0:
                        print(f"   回撤机会发现: {entry_opportunities}个")
                    if invalidations > 0:
                        print(f"   回撤失效: {invalidations}个")
                    if waiting > 0:
                        print(f"   等待回撤: {waiting}个")
                
                # 统计不同类型的组合
                # combinations 是 KLineCombination 对象列表，需要使用属性访问
                bullish_combinations = []
                bearish_combinations = []
                
                for combo in combinations:
                    # 根据 pattern_type 或 description 判断看涨/看跌
                    if hasattr(combo, 'pattern_type'):
                        if '看涨' in combo.pattern_name or '看涨' in combo.description:
                            bullish_combinations.append(combo)
                        elif '看跌' in combo.pattern_name or '看跌' in combo.description:
                            bearish_combinations.append(combo)
                        else:
                            # 根据信号方向判断
                            if combo.entry_price > 0:  # 简单判断
                                if '上' in combo.description or 'bullish' in combo.pattern_type.lower():
                                    bullish_combinations.append(combo)
                                else:
                                    bearish_combinations.append(combo)
                
                # 简化统计
                close_above_open = sum(1 for c in bullish_combinations if '收盘>前开盘' in c.description)
                high_above_high = sum(1 for c in bullish_combinations if '高点>前高点' in c.description)
                
                close_below_open = sum(1 for c in bearish_combinations if '收盘<前开盘' in c.description)
                low_below_low = sum(1 for c in bearish_combinations if '低点<前低点' in c.description)
                
                if bullish_combinations:
                    print(f"   看涨组合条件: {len(bullish_combinations)}个")
                    if close_above_open > 0:
                        print(f"   看涨收盘>前开盘: {close_above_open}个")
                    if high_above_high > 0:
                        print(f"   看涨高点>前高点: {high_above_high}个")
                if bearish_combinations:
                    print(f"   看跌组合条件: {len(bearish_combinations)}个")
                    if close_below_open > 0:
                        print(f"   看跌收盘<前开盘: {close_below_open}个")
                    if low_below_low > 0:
                        print(f"   看跌低点<前低点: {low_below_low}个")
                
                # 过滤统计
                filter_stats = analysis_result.get('filter_stats', {})
                if filter_stats:
                    print("\n📊 阶段2过滤统计:")
                    initial = filter_stats.get('initial_signals', 0)
                    shadow_passed = filter_stats.get('shadow_filter_passed', 0)
                    shadow_rejected = filter_stats.get('shadow_filter_rejected', 0)
                    atr_passed = filter_stats.get('atr_filter_passed', 0)
                    atr_rejected = filter_stats.get('atr_filter_rejected', 0)
                    final = filter_stats.get('final_signals', 0)
                    
                    print(f"   初始信号: {initial}个")
                    if initial > 0:
                        shadow_rate = (shadow_passed / initial * 100) if initial > 0 else 0
                        atr_rate = (atr_passed / initial * 100) if initial > 0 else 0
                        final_rate = (final / initial * 100) if initial > 0 else 0
                        
                        print(f"   影线过滤: 通过{shadow_passed}个, 拒绝{shadow_rejected}个 (通过率:{shadow_rate:.1f}%)")
                        print(f"   ATR过滤: 通过{atr_passed}个, 拒绝{atr_rejected}个 (通过率:{atr_rate:.1f}%)")
                        print(f"   最终信号: {final}个 (总通过率:{final_rate:.1f}%)")
                        print(f"   信号净化率: {100-final_rate:.1f}% (过滤掉{initial-final}个低质量信号)")
                
                # 计算胜率（简化版）
                if trading_signals:
                    print("\n📊 交易信号统计:")
                    # 简单的胜率计算逻辑
                    wins = 0
                    losses = 0
                    for i, signal in enumerate(trading_signals):
                        # 简单模拟：看后续10根K线
                        signal_index = signal['index']
                        if signal_index + 10 < len(data):
                            # 检查后续价格走势
                            future_data = data.iloc[signal_index:signal_index+10]
                            if signal['is_bullish']:
                                # 看涨信号：检查是否上涨
                                if future_data['high'].max() > signal['entry_price'] * 1.001:
                                    wins += 1
                                else:
                                    losses += 1
                            else:
                                # 看跌信号：检查是否下跌
                                if future_data['low'].min() < signal['entry_price'] * 0.999:
                                    wins += 1
                                else:
                                    losses += 1
                    
                    if wins + losses > 0:
                        win_rate = wins / (wins + losses) * 100
                        print(f"   预估胜率: {win_rate:.1f}% (基于简单价格走势)")
                
                print("\n✅ 计算完成（未显示图表）")
            
            elif command.startswith("more") and session:
                parts = command.split()
                count = int(parts[1]) if len(parts) > 1 else 500
                session.load_more_history(count)
            
            elif command.startswith("support") and session:
                parts = command.split()
                if len(parts) > 1:
                    try:
                        price = float(parts[1])
                        session.add_support_resistance([(price, '支撑线')])
                        print(f"✅ 已添加支撑线: {price}")
                    except ValueError:
                        print("❌ 请输入有效的价格数字")
            
            elif command.startswith("resist") and session:
                parts = command.split()
                if len(parts) > 1:
                    try:
                        price = float(parts[1])
                        session.add_support_resistance([(price, '阻力线')])
                        print(f"✅ 已添加阻力线: {price}")
                    except ValueError:
                        print("❌ 请输入有效的价格数字")
            
            elif command.startswith("range") and session:
                parts = command.split()
                if len(parts) >= 3:
                    start_date = parts[1]
                    end_date = parts[2]
                    session.load_date_range(start_date, end_date)
                else:
                    print("❌ 请提供开始和结束日期，如: range 2024-01-01 2024-03-31")
            
            elif command == "analyze" and session:
                print("🔍 执行PA分析...")
                session.update(analyze=True)
            
            elif command == "clear" and session:
                session.clear_overlays()
                session.update()
            
            elif command == "status":
                if session:
                    status = session.get_status()
                    print(f"\n📊 会话状态:")
                    print(f"  品种: {status['symbol']} {status['timeframe']}")
                    print(f"  K线数量: {status['data_count']}")
                    print(f"  缓存大小: {status['cache_size_mb']:.2f} MB")
                    print(f"  叠加层: {status['overlays_count']}个")
                    print(f"  指标: {', '.join(status['indicators']) if status['indicators'] else '无'}")
                else:
                    print("❌ 请先使用 'show' 命令创建会话")
            
            elif command == "":
                continue
            
            else:
                if session is None:
                    print("❌ 请先使用 'show' 命令显示图表")
                else:
                    print(f"❌ 未知命令: {command}，输入 'help' 查看帮助")
        
        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


def quick_show(symbol="EUR/USD", timeframe="15min", count=1000, analyze=True):
    """
    快速显示模式 - 直接显示图表
    
    Args:
        symbol: 交易品种
        timeframe: 时间周期
        count: K线数量
        analyze: 是否进行PA分析
    """
    print("="*60)
    print("📊 LLM交易分析系统 - 快速显示模式")
    print("="*60)
    
    session = PA_ChartSession(symbol=symbol, timeframe=timeframe)
    session.show(count=count, analyze=analyze)
    
    print("\n图表已显示")
    print("提示: 使用 'python3 main.py' 进入交互模式可进行更多操作")
    
    try:
        input("\n按Enter键退出...")
    except (KeyboardInterrupt, EOFError):
        pass
    
    print("👋 再见！")


def performance_test():
    """性能测试模式"""
    print("="*60)
    print("🧪 性能测试模式")
    print("="*60)
    
    session = PA_ChartSession()
    
    # 测试1：首次加载
    print("\n📊 测试1：首次加载1000根K线")
    start = time.time()
    session.show(count=1000, analyze=False)
    elapsed = time.time() - start
    print(f"⏱️ 首次加载耗时: {elapsed:.2f}秒")
    
    time.sleep(1)
    
    # 测试2：添加支撑阻力
    print("\n📊 测试2：添加支撑阻力线")
    start = time.time()
    session.add_support_resistance([
        (1.0800, '支撑'),
        (1.0900, '阻力')
    ])
    elapsed = time.time() - start
    print(f"⏱️ 添加支撑阻力耗时: {elapsed:.2f}秒")
    
    time.sleep(1)
    
    # 测试3：加载更多数据
    print("\n📊 测试3：加载额外500根K线")
    start = time.time()
    session.load_more_history(500)
    elapsed = time.time() - start
    print(f"⏱️ 加载更多数据耗时: {elapsed:.2f}秒")
    
    # 显示统计
    status = session.get_status()
    print(f"\n📊 最终状态:")
    print(f"  K线总数: {status['data_count']}")
    print(f"  缓存大小: {status['cache_size_mb']:.2f} MB")
    
    print("\n✅ 性能测试完成！")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='LLM交易分析系统 - 智能交易分析和图表显示',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 main.py                          # 交互式模式（默认）
  python3 main.py --mode show              # 快速显示模式
  python3 main.py --mode show --count 500  # 显示500根K线
  python3 main.py --mode perf              # 性能测试模式
  python3 main.py --symbol GBP/USD         # 分析英镑/美元
        """
    )
    
    parser.add_argument('--mode', 
                       choices=['interactive', 'show', 'perf'],
                       default='interactive',
                       help='运行模式 (默认: interactive)')
    
    parser.add_argument('--symbol',
                       default='EUR/USD',
                       help='交易品种 (默认: EUR/USD)')
    
    parser.add_argument('--timeframe',
                       default='15min',
                       choices=['15min', '1h', '4h', '1day'],
                       help='时间周期 (默认: 15min)')
    
    parser.add_argument('--count',
                       type=int,
                       default=1000,
                       help='K线数量 (默认: 1000)')
    
    parser.add_argument('--no-analyze',
                       action='store_true',
                       help='跳过PA分析')
    
    args = parser.parse_args()
    
    try:
        if args.mode == 'interactive':
            interactive_mode(args.symbol, args.timeframe)
        elif args.mode == 'show':
            quick_show(args.symbol, args.timeframe, args.count, not args.no_analyze)
        elif args.mode == 'perf':
            performance_test()
    except KeyboardInterrupt:
        print("\n\n👋 程序已退出")
    except Exception as e:
        print(f"\n❌ 程序错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()