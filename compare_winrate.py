#!/usr/bin/env python3
"""
使用main.py的calc命令对比影线过滤的胜率变化
"""

import subprocess
import re

def run_calc_command(command):
    """运行calc命令并提取胜率信息"""
    print(f"\n{'='*50}")
    print(f"运行命令: {command}")
    print('='*50)
    
    # 运行main.py
    process = subprocess.Popen(
        ['python3', 'main.py'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 发送命令
    stdout, stderr = process.communicate(input=f"{command}\nquit\n", timeout=30)
    
    print(stdout)
    
    # 提取关键信息
    info = {
        '初始信号': 0,
        '最终信号': 0,
        '胜率': 0.0,
        '过滤率': 0.0
    }
    
    # 解析输出
    lines = stdout.split('\n')
    for line in lines:
        if '初始信号:' in line:
            match = re.search(r'初始信号:\s*(\d+)个', line)
            if match:
                info['初始信号'] = int(match.group(1))
        
        if '最终信号:' in line:
            match = re.search(r'最终信号:\s*(\d+)个', line)
            if match:
                info['最终信号'] = int(match.group(1))
        
        if '预估胜率:' in line:
            match = re.search(r'预估胜率:\s*([\d.]+)%', line)
            if match:
                info['胜率'] = float(match.group(1))
        
        if '总通过率:' in line:
            match = re.search(r'总通过率:([\d.]+)%', line)
            if match:
                pass_rate = float(match.group(1))
                info['过滤率'] = 100.0 - pass_rate
    
    return info

def main():
    print("🔍 对比自定义ATR倍数对胜率的影响（基于5000根K线）")
    print("测试ATR倍数从0.5到2.0的效果，间隔0.1")
    
    # 测试命令 - ATR倍数从0.5到2.0，间隔0.1
    tests = [("calc 5000", "无过滤（基准）")]
    
    # 生成ATR倍数测试（0.5到2.0，间隔0.1）
    for mult in [round(0.5 + i * 0.1, 1) for i in range(16)]:
        tests.append((f"calc 5000 atr_mult={mult}", f"ATR倍数{mult}"))
    
    print(f"将测试{len(tests)}个ATR倍数条件（0.5-2.0，间隔0.1）")
    
    # 保留影线测试（以后可能需要）
    # wick_tests = [
    #     ("calc 5000 wick=0.3", "影线过滤30%"),
    #     ("calc 5000 wick=0.25", "影线过滤25%"), 
    #     ("calc 5000 wick=0.2", "影线过滤20%"),
    #     ("calc 5000 wick=0.15", "影线过滤15%"),
    # ]
    
    results = []
    for command, description in tests:
        result = run_calc_command(command)
        result['描述'] = description
        results.append(result)
    
    # 输出对比结果
    print(f"\n{'='*80}")
    print("📊 胜率对比结果汇总")
    print('='*80)
    
    print(f"{'设置':<15} | {'初始信号':<8} | {'最终信号':<8} | {'过滤率':<8} | {'胜率':<8}")
    print('-'*70)
    
    for result in results:
        print(f"{result['描述']:<15} | {result['初始信号']:<8} | {result['最终信号']:<8} | {result['过滤率']:<8.1f}% | {result['胜率']:<8.1f}%")
    
    # 分析结论
    print(f"\n📈 分析结论:")
    baseline = results[0]  # 无过滤作为基准
    
    print(f"基准胜率（无过滤）: {baseline['胜率']:.1f}%")
    
    for i, result in enumerate(results[1:], 1):
        winrate_change = result['胜率'] - baseline['胜率']
        signal_reduction = baseline['最终信号'] - result['最终信号']
        
        print(f"{result['描述']}: 胜率{result['胜率']:.1f}% ({winrate_change:+.1f}%), 减少{signal_reduction}个信号")
    
    print("\n✅ 对比测试完成！")

if __name__ == "__main__":
    main()