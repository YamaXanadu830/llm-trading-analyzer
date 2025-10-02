#!/usr/bin/env python3
"""
参数敏感性分析器 - 专门针对LLM交易分析系统进行参数优化
基于现有compare_winrate.py扩展，提供全面的参数分析功能
"""

import subprocess
import re
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import os
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass
import time

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


@dataclass
class ParameterTestResult:
    """参数测试结果"""
    config: str              # 配置字符串
    description: str         # 描述
    initial_signals: int     # 初始信号数
    final_signals: int       # 最终信号数
    win_rate: float          # 胜率
    filter_rate: float       # 过滤率
    signal_density: float    # 信号密度
    score: float            # 综合评分


class ParameterAnalyzer:
    """参数分析器"""
    
    def __init__(self, data_count: int = 5000):
        self.data_count = data_count
        self.results = []
        
        # 创建结果目录
        self.results_dir = "parameter_analysis_results"
        os.makedirs(self.results_dir, exist_ok=True)
        
        print(f"🔬 参数分析器初始化完成")
        print(f"   数据量: {data_count} 根K线")
        print(f"   结果目录: {self.results_dir}")
    
    def run_comprehensive_analysis(self):
        """运行全面的参数分析"""
        print(f"\n{'='*60}")
        print(f"🔍 开始全面参数敏感性分析")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        # 阶段1：ATR参数分析
        print(f"\n📊 阶段1: ATR参数敏感性分析")
        atr_results = self._analyze_atr_parameters()
        
        # 阶段2：影线长度分析
        print(f"\n📏 阶段2: 影线长度敏感性分析")
        wick_results = self._analyze_wick_parameters()
        
        # 阶段3：K线周期分析
        print(f"\n📈 阶段3: K线回看周期分析")
        kline_results = self._analyze_kline_parameters()
        
        # 阶段4：组合参数分析
        print(f"\n🔗 阶段4: 最优参数组合分析")
        combo_results = self._analyze_parameter_combinations(atr_results, wick_results, kline_results)
        
        # 阶段5：过拟合检验
        print(f"\n✅ 阶段5: 参数稳定性检验")
        stability_results = self._stability_analysis(combo_results[:5])  # 测试前5个最优组合
        
        # 生成报告
        end_time = time.time()
        self._generate_comprehensive_report(atr_results, wick_results, kline_results, combo_results, stability_results)
        
        print(f"\n🎉 参数分析完成! 总耗时: {end_time - start_time:.1f}秒")
        print(f"📋 详细报告: {self.results_dir}/parameter_analysis_report.md")
    
    def _run_calc_command(self, command: str) -> ParameterTestResult:
        """运行calc命令并解析结果"""
        try:
            print(f"  执行: {command}")
            
            # 运行main.py
            process = subprocess.Popen(
                ['python3', 'main.py'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd='/Users/xanadu/Downloads/CodeProjects/llm-trading-analyzer'
            )
            
            # 发送命令
            stdout, stderr = process.communicate(input=f"{command}\nquit\n", timeout=60)
            
            if stderr:
                print(f"    ⚠️ 警告: {stderr[:200]}...")
            
            # 解析结果
            result = self._parse_output(stdout, command)
            print(f"    胜率: {result.win_rate:.1f}%, 信号: {result.final_signals}, 过滤率: {result.filter_rate:.1f}%")
            
            return result
            
        except subprocess.TimeoutExpired:
            print(f"    ❌ 命令超时: {command}")
            return self._empty_result(command)
        except Exception as e:
            print(f"    ❌ 执行错误: {e}")
            return self._empty_result(command)
    
    def _parse_output(self, stdout: str, command: str) -> ParameterTestResult:
        """解析命令输出"""
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
        
        # 计算信号密度和综合评分
        signal_density = info['最终信号'] / self.data_count * 1000 if self.data_count > 0 else 0
        
        # 综合评分: 胜率权重0.6 + 信号密度权重0.4（密度标准化到0-100）
        normalized_density = min(signal_density * 10, 100)  # 10个信号/1000根 = 100分
        score = info['胜率'] * 0.6 + normalized_density * 0.4
        
        return ParameterTestResult(
            config=command,
            description=self._get_command_description(command),
            initial_signals=info['初始信号'],
            final_signals=info['最终信号'],
            win_rate=info['胜率'],
            filter_rate=info['过滤率'],
            signal_density=signal_density,
            score=score
        )
    
    def _get_command_description(self, command: str) -> str:
        """获取命令描述"""
        if 'atr_mult=' in command:
            match = re.search(r'atr_mult=([\d.]+)', command)
            if match:
                return f"ATR倍数{match.group(1)}"
        
        if 'wick=' in command:
            match = re.search(r'wick=([\d.]+)', command)
            if match:
                return f"影线过滤{float(match.group(1))*100:.0f}%"
        
        if 'atr_period=' in command:
            match = re.search(r'atr_period=(\d+)', command)
            if match:
                return f"ATR周期{match.group(1)}"
        
        if 'k_line_value=' in command:
            match = re.search(r'k_line_value=(\d+)', command)
            if match:
                return f"K线周期{match.group(1)}"
        
        if command.strip() == f"calc {self.data_count}":
            return "无过滤（基准）"
        
        return "组合参数"
    
    def _empty_result(self, command: str) -> ParameterTestResult:
        """返回空结果"""
        return ParameterTestResult(
            config=command,
            description=self._get_command_description(command),
            initial_signals=0,
            final_signals=0,
            win_rate=0.0,
            filter_rate=0.0,
            signal_density=0.0,
            score=0.0
        )
    
    def _analyze_atr_parameters(self) -> List[ParameterTestResult]:
        """分析ATR参数"""
        print(f"🔍 测试ATR相关参数...")
        
        tests = [
            (f"calc {self.data_count}", "无过滤基准"),
        ]
        
        # ATR倍数测试（关键几个值）
        atr_multipliers = [0.8, 1.0, 1.2, 1.5, 2.0, 2.5]  # 精选关键参数
        for mult in atr_multipliers:
            tests.append((f"calc {self.data_count} atr_mult={mult}", f"ATR倍数{mult}"))
        
        # ATR周期测试（减少测试数量）
        atr_periods = [10, 14, 20]
        for period in atr_periods:
            tests.append((f"calc {self.data_count} atr_period={period}", f"ATR周期{period}"))
        
        print(f"   总共测试 {len(tests)} 个ATR配置")
        
        results = []
        for command, desc in tests:
            result = self._run_calc_command(command)
            results.append(result)
        
        # 按综合评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        print(f"\n📊 ATR参数分析结果（前5名）:")
        for i, result in enumerate(results[:5]):
            print(f"   {i+1}. {result.description}: 胜率{result.win_rate:.1f}% 信号{result.final_signals} 评分{result.score:.1f}")
        
        return results
    
    def _analyze_wick_parameters(self) -> List[ParameterTestResult]:
        """分析影线参数"""
        print(f"🔍 测试影线过滤参数...")
        
        # 影线比例测试（0到1.0，间隔0.1，重点测试0.1-0.5）
        wick_ratios = [0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.8, 1.0]
        
        tests = []
        for ratio in wick_ratios:
            if ratio == 0.0:
                tests.append((f"calc {self.data_count}", "无影线过滤"))
            else:
                tests.append((f"calc {self.data_count} wick={ratio}", f"影线过滤{ratio*100:.0f}%"))
        
        print(f"   总共测试 {len(tests)} 个影线配置")
        
        results = []
        for command, desc in tests:
            result = self._run_calc_command(command)
            results.append(result)
        
        # 按综合评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        print(f"\n📊 影线参数分析结果（前5名）:")
        for i, result in enumerate(results[:5]):
            print(f"   {i+1}. {result.description}: 胜率{result.win_rate:.1f}% 信号{result.final_signals} 评分{result.score:.1f}")
        
        return results
    
    def _analyze_kline_parameters(self) -> List[ParameterTestResult]:
        """分析K线周期参数"""
        print(f"🔍 测试K线回看周期参数...")
        
        # K线周期测试
        kline_values = [3, 5, 8, 10, 13, 15, 21, 25, 30, 34]
        
        tests = []
        for value in kline_values:
            tests.append((f"calc {self.data_count} k_line_value={value}", f"K线周期{value}"))
        
        print(f"   总共测试 {len(tests)} 个K线周期配置")
        
        results = []
        for command, desc in tests:
            result = self._run_calc_command(command)
            results.append(result)
        
        # 按综合评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        print(f"\n📊 K线周期参数分析结果（前5名）:")
        for i, result in enumerate(results[:5]):
            print(f"   {i+1}. {result.description}: 胜率{result.win_rate:.1f}% 信号{result.final_signals} 评分{result.score:.1f}")
        
        return results
    
    def _analyze_parameter_combinations(self, atr_results: List[ParameterTestResult], 
                                      wick_results: List[ParameterTestResult],
                                      kline_results: List[ParameterTestResult]) -> List[ParameterTestResult]:
        """分析参数组合"""
        print(f"🔍 测试最优参数组合...")
        
        # 从每个类别选择前3个最优参数
        top_atr = atr_results[1:4]  # 跳过基准，取前3
        top_wick = wick_results[1:4] if len(wick_results) > 3 else wick_results[1:]
        top_kline = kline_results[:3]
        
        combinations = []
        
        # 两参数组合
        for atr in top_atr[:2]:  # 只取前2个ATR
            for wick in top_wick[:2]:  # 只取前2个影线
                atr_param = self._extract_parameter(atr.config, 'atr_mult')
                wick_param = self._extract_parameter(wick.config, 'wick')
                
                if atr_param and wick_param and wick_param != "0":
                    command = f"calc {self.data_count} atr_mult={atr_param} wick={wick_param}"
                    combinations.append((command, f"ATR{atr_param}+影线{float(wick_param)*100:.0f}%"))
        
        # 三参数组合（只测试最优的几个）
        if top_atr and top_wick and top_kline:
            atr_param = self._extract_parameter(top_atr[0].config, 'atr_mult')
            wick_param = self._extract_parameter(top_wick[0].config, 'wick')
            kline_param = self._extract_parameter(top_kline[0].config, 'k_line_value')
            
            if atr_param and wick_param and kline_param and wick_param != "0":
                command = f"calc {self.data_count} atr_mult={atr_param} wick={wick_param} k_line_value={kline_param}"
                combinations.append((command, f"ATR{atr_param}+影线{float(wick_param)*100:.0f}%+K线{kline_param}"))
        
        print(f"   总共测试 {len(combinations)} 个参数组合")
        
        results = []
        for command, desc in combinations:
            result = self._run_calc_command(command)
            result.description = desc  # 更新描述
            results.append(result)
        
        # 按综合评分排序
        results.sort(key=lambda x: x.score, reverse=True)
        
        print(f"\n📊 参数组合分析结果:")
        for i, result in enumerate(results):
            print(f"   {i+1}. {result.description}: 胜率{result.win_rate:.1f}% 信号{result.final_signals} 评分{result.score:.1f}")
        
        return results
    
    def _extract_parameter(self, config: str, param_name: str) -> str:
        """从配置字符串中提取参数值"""
        pattern = f'{param_name}=([\\d.]+)'
        match = re.search(pattern, config)
        return match.group(1) if match else None
    
    def _stability_analysis(self, top_configs: List[ParameterTestResult]) -> List[Dict]:
        """稳定性分析 - 使用不同数据量测试参数稳定性"""
        print(f"🔍 对前{len(top_configs)}个配置进行稳定性测试...")
        
        stability_results = []
        test_data_counts = [2000, 3000, 4000]  # 不同的数据量
        
        for config in top_configs:
            print(f"  测试配置: {config.description}")
            
            # 提取参数并构建命令
            base_command = config.config.replace(f"calc {self.data_count}", "calc")
            
            config_results = []
            for data_count in test_data_counts:
                test_command = f"calc {data_count}" + base_command[4:]  # 替换数据量部分
                result = self._run_calc_command(test_command)
                config_results.append(result)
                print(f"    数据量{data_count}: 胜率{result.win_rate:.1f}% 信号{result.final_signals}")
            
            # 计算稳定性指标
            win_rates = [r.win_rate for r in config_results]
            signal_densities = [r.signal_density for r in config_results]
            
            win_rate_std = np.std(win_rates)
            signal_density_std = np.std(signal_densities)
            
            # 稳定性评分（标准差越小越稳定）
            stability_score = max(0, 100 - win_rate_std * 2 - signal_density_std)
            
            stability_results.append({
                'config': config,
                'test_results': config_results,
                'win_rate_std': win_rate_std,
                'signal_density_std': signal_density_std,
                'stability_score': stability_score,
                'avg_win_rate': np.mean(win_rates),
                'avg_signal_density': np.mean(signal_densities)
            })
            
            print(f"    稳定性评分: {stability_score:.1f} (胜率标准差: {win_rate_std:.1f})")
        
        # 按稳定性评分排序
        stability_results.sort(key=lambda x: x['stability_score'], reverse=True)
        
        return stability_results
    
    def _generate_comprehensive_report(self, atr_results: List[ParameterTestResult],
                                     wick_results: List[ParameterTestResult],
                                     kline_results: List[ParameterTestResult],
                                     combo_results: List[ParameterTestResult],
                                     stability_results: List[Dict]):
        """生成全面分析报告"""
        report_path = os.path.join(self.results_dir, 'parameter_analysis_report.md')
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# LLM交易分析系统 - 参数敏感性分析报告\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"测试数据量: {self.data_count} 根K线\n\n")
            
            # 执行摘要
            f.write("## 📊 执行摘要\n\n")
            if combo_results:
                best_combo = combo_results[0]
                f.write(f"**最优参数组合**: {best_combo.description}\n")
                f.write(f"- 胜率: {best_combo.win_rate:.1f}%\n")
                f.write(f"- 信号数: {best_combo.final_signals}\n")
                f.write(f"- 信号密度: {best_combo.signal_density:.1f} 个/1000根K线\n")
                f.write(f"- 综合评分: {best_combo.score:.1f}\n\n")
            
            # ATR参数分析
            f.write("## 🔍 ATR参数分析\n\n")
            f.write("| 排名 | 配置 | 胜率(%) | 信号数 | 过滤率(%) | 评分 |\n")
            f.write("|------|------|---------|--------|-----------|------|\n")
            for i, result in enumerate(atr_results[:10]):
                f.write(f"| {i+1} | {result.description} | {result.win_rate:.1f} | {result.final_signals} | "
                       f"{result.filter_rate:.1f} | {result.score:.1f} |\n")
            f.write("\n")
            
            # 影线参数分析
            f.write("## 📏 影线长度分析\n\n")
            f.write("| 排名 | 配置 | 胜率(%) | 信号数 | 过滤率(%) | 评分 |\n")
            f.write("|------|------|---------|--------|-----------|------|\n")
            for i, result in enumerate(wick_results[:10]):
                f.write(f"| {i+1} | {result.description} | {result.win_rate:.1f} | {result.final_signals} | "
                       f"{result.filter_rate:.1f} | {result.score:.1f} |\n")
            f.write("\n")
            
            # K线周期分析
            f.write("## 📈 K线回看周期分析\n\n")
            f.write("| 排名 | 配置 | 胜率(%) | 信号数 | 评分 |\n")
            f.write("|------|------|---------|--------|---------|\n")
            for i, result in enumerate(kline_results[:10]):
                f.write(f"| {i+1} | {result.description} | {result.win_rate:.1f} | {result.final_signals} | "
                       f"{result.score:.1f} |\n")
            f.write("\n")
            
            # 参数组合分析
            f.write("## 🔗 参数组合优化\n\n")
            if combo_results:
                f.write("| 排名 | 配置组合 | 胜率(%) | 信号数 | 评分 |\n")
                f.write("|------|----------|---------|--------|---------|\n")
                for i, result in enumerate(combo_results):
                    f.write(f"| {i+1} | {result.description} | {result.win_rate:.1f} | {result.final_signals} | "
                           f"{result.score:.1f} |\n")
                f.write("\n")
            
            # 稳定性分析
            f.write("## ✅ 稳定性分析\n\n")
            if stability_results:
                f.write("| 配置 | 平均胜率(%) | 胜率标准差 | 稳定性评分 |\n")
                f.write("|------|-------------|------------|------------|\n")
                for result in stability_results:
                    f.write(f"| {result['config'].description} | {result['avg_win_rate']:.1f} | "
                           f"{result['win_rate_std']:.1f} | {result['stability_score']:.1f} |\n")
                f.write("\n")
            
            # 参数使用建议
            f.write("## 💡 参数使用建议\n\n")
            
            # 高胜率策略
            high_winrate = [r for r in combo_results + atr_results + wick_results if r.win_rate >= 70]
            if high_winrate:
                best_hr = max(high_winrate, key=lambda x: x.win_rate)
                f.write("### 🎯 高胜率策略 (≥70%)\n")
                f.write(f"**推荐配置**: {best_hr.description}\n")
                f.write(f"- 预期胜率: {best_hr.win_rate:.1f}%\n")
                f.write(f"- 信号密度: {best_hr.signal_density:.1f} 个/1000根K线\n")
                f.write(f"- 使用场景: 追求高胜率，可接受较低交易频率\n\n")
            
            # 高频策略
            high_frequency = [r for r in combo_results + atr_results + wick_results if r.signal_density >= 8]
            if high_frequency:
                best_hf = max(high_frequency, key=lambda x: x.signal_density)
                f.write("### ⚡ 高频交易策略 (≥8信号/1000根K线)\n")
                f.write(f"**推荐配置**: {best_hf.description}\n")
                f.write(f"- 预期胜率: {best_hf.win_rate:.1f}%\n")
                f.write(f"- 信号密度: {best_hf.signal_density:.1f} 个/1000根K线\n")
                f.write(f"- 使用场景: 追求交易频率，可接受中等胜率\n\n")
            
            # 平衡策略
            if combo_results:
                best_balanced = combo_results[0]
                f.write("### ⚖️ 平衡策略 (推荐)\n")
                f.write(f"**推荐配置**: {best_balanced.description}\n")
                f.write(f"- 预期胜率: {best_balanced.win_rate:.1f}%\n")
                f.write(f"- 信号密度: {best_balanced.signal_density:.1f} 个/1000根K线\n")
                f.write(f"- 综合评分: {best_balanced.score:.1f}\n")
                f.write(f"- 使用场景: 胜率和交易频率的最佳平衡点\n\n")
            
            # 避免过拟合建议
            f.write("## ⚠️ 避免过拟合建议\n\n")
            f.write("1. **参数稳定性**: 优选在不同数据量下表现稳定的参数\n")
            f.write("2. **简单性原则**: 避免过度复杂的参数组合\n")
            f.write("3. **定期验证**: 建议每月重新评估参数有效性\n")
            f.write("4. **样本充足**: 确保测试有足够的历史数据\n\n")
            
            # 实际使用命令
            f.write("## 🛠️ 实际使用命令\n\n")
            if combo_results:
                best_config = combo_results[0]
                # 提取参数并生成calc命令
                command_params = []
                if 'atr_mult=' in best_config.config:
                    atr_param = self._extract_parameter(best_config.config, 'atr_mult')
                    if atr_param:
                        command_params.append(f"atr_mult={atr_param}")
                
                if 'wick=' in best_config.config:
                    wick_param = self._extract_parameter(best_config.config, 'wick')
                    if wick_param:
                        command_params.append(f"wick={wick_param}")
                
                if 'k_line_value=' in best_config.config:
                    kline_param = self._extract_parameter(best_config.config, 'k_line_value')
                    if kline_param:
                        command_params.append(f"k_line_value={kline_param}")
                
                if command_params:
                    f.write(f"**最优配置命令**:\n")
                    f.write(f"```bash\n")
                    f.write(f"python3 main.py\n")
                    f.write(f"> calc 1000 {' '.join(command_params)}\n")
                    f.write(f"```\n\n")
        
        # 保存详细数据
        all_results = {
            'atr_results': [r.__dict__ for r in atr_results],
            'wick_results': [r.__dict__ for r in wick_results],
            'kline_results': [r.__dict__ for r in kline_results],
            'combo_results': [r.__dict__ for r in combo_results],
            'stability_results': stability_results,
            'analysis_time': datetime.now().isoformat(),
            'data_count': self.data_count
        }
        
        json_path = os.path.join(self.results_dir, 'parameter_analysis_data.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
        
        # 创建可视化
        self._create_visualizations(atr_results, wick_results, kline_results, combo_results)
        
        print(f"\n📋 分析报告已生成: {report_path}")
        print(f"📊 详细数据已保存: {json_path}")
        print(f"📈 可视化图表: {self.results_dir}/parameter_analysis_charts.png")
    
    def _create_visualizations(self, atr_results: List[ParameterTestResult],
                             wick_results: List[ParameterTestResult],
                             kline_results: List[ParameterTestResult],
                             combo_results: List[ParameterTestResult]):
        """创建可视化图表"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('LLM交易分析系统 - 参数敏感性分析', fontsize=16)
        
        # 图1: ATR参数敏感性
        if atr_results:
            atr_descriptions = [r.description for r in atr_results[:10]]
            atr_scores = [r.score for r in atr_results[:10]]
            
            ax1.barh(range(len(atr_descriptions)), atr_scores, color='skyblue')
            ax1.set_yticks(range(len(atr_descriptions)))
            ax1.set_yticklabels(atr_descriptions, fontsize=8)
            ax1.set_xlabel('综合评分')
            ax1.set_title('ATR参数敏感性分析')
            ax1.grid(True, alpha=0.3)
        
        # 图2: 影线参数敏感性
        if wick_results:
            wick_descriptions = [r.description for r in wick_results[:10]]
            wick_scores = [r.score for r in wick_results[:10]]
            
            ax2.barh(range(len(wick_descriptions)), wick_scores, color='lightgreen')
            ax2.set_yticks(range(len(wick_descriptions)))
            ax2.set_yticklabels(wick_descriptions, fontsize=8)
            ax2.set_xlabel('综合评分')
            ax2.set_title('影线参数敏感性分析')
            ax2.grid(True, alpha=0.3)
        
        # 图3: 胜率vs信号密度散点图
        all_results = atr_results + wick_results + kline_results
        if all_results:
            win_rates = [r.win_rate for r in all_results]
            signal_densities = [r.signal_density for r in all_results]
            
            scatter = ax3.scatter(signal_densities, win_rates, c=[r.score for r in all_results], 
                                cmap='viridis', alpha=0.7, s=50)
            ax3.set_xlabel('信号密度 (个/1000根K线)')
            ax3.set_ylabel('胜率 (%)')
            ax3.set_title('胜率 vs 信号密度 (颜色表示综合评分)')
            ax3.grid(True, alpha=0.3)
            plt.colorbar(scatter, ax=ax3)
        
        # 图4: 最优组合对比
        if combo_results:
            combo_descriptions = [r.description for r in combo_results]
            combo_win_rates = [r.win_rate for r in combo_results]
            combo_signals = [r.final_signals for r in combo_results]
            
            x = range(len(combo_descriptions))
            width = 0.35
            
            ax4_twin = ax4.twinx()
            bars1 = ax4.bar([i - width/2 for i in x], combo_win_rates, width, 
                           label='胜率(%)', color='orange', alpha=0.7)
            bars2 = ax4_twin.bar([i + width/2 for i in x], combo_signals, width, 
                                label='信号数', color='purple', alpha=0.7)
            
            ax4.set_xlabel('参数组合配置')
            ax4.set_ylabel('胜率 (%)', color='orange')
            ax4_twin.set_ylabel('信号数', color='purple')
            ax4.set_title('最优参数组合对比')
            ax4.set_xticks(x)
            ax4.set_xticklabels(combo_descriptions, rotation=45, ha='right', fontsize=8)
            ax4.legend(loc='upper left')
            ax4_twin.legend(loc='upper right')
        
        plt.tight_layout()
        
        # 保存图表
        chart_path = os.path.join(self.results_dir, 'parameter_analysis_charts.png')
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()


def main():
    """主函数"""
    print("🔬 LLM交易分析系统 - 参数敏感性分析器")
    print("=" * 60)
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='参数敏感性分析器')
    parser.add_argument('--data-count', type=int, default=5000, 
                       help='使用的K线数据量 (默认: 5000)')
    parser.add_argument('--quick', action='store_true', 
                       help='快速测试模式（减少测试参数数量）')
    
    args = parser.parse_args()
    
    try:
        analyzer = ParameterAnalyzer(data_count=args.data_count)
        
        if args.quick:
            # 快速模式：只测试关键参数
            print("⚡ 快速测试模式")
            # 这里可以添加快速测试的逻辑
        
        analyzer.run_comprehensive_analysis()
        
    except KeyboardInterrupt:
        print(f"\n⏸️ 分析被用户中断")
    except Exception as e:
        print(f"\n❌ 分析过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()