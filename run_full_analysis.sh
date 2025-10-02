#!/bin/bash
echo "🔬 开始LLM交易分析系统参数分析 (30000根K线)"
echo "开始时间: $(date)"
echo "预计耗时: 20-30分钟"
echo "================================"

cd /Users/xanadu/Downloads/CodeProjects/llm-trading-analyzer

# 运行完整分析
python3 parameter_analysis.py --data-count 30000

echo "================================"
echo "✅ 分析完成!"
echo "结束时间: $(date)"
echo ""
echo "📂 生成的结果文件:"
echo "   📋 parameter_analysis_results/parameter_analysis_report.md"
echo "   📊 parameter_analysis_results/parameter_analysis_data.json" 
echo "   📈 parameter_analysis_results/parameter_analysis_charts.png"
echo ""
echo "🔍 查看结果:"
echo "   cat parameter_analysis_results/parameter_analysis_report.md"