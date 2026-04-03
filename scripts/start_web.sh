#!/bin/bash
# LinguaLearn Web Server 启动脚本（conda automation 环境）
set -euo pipefail

echo "🎓 LinguaLearn - 多语言学习视频生成系统"
echo "==========================================="

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件"
    echo "OPENAI_API_KEY=your_key_here" > .env
    echo "OPENAI_BASE_URL=https://api.deepseek.com" >> .env
    echo "📋 已创建 .env，请填入您的 API Key 后重新运行"
    exit 1
fi

# 创建必要目录（统一迁移到 data/）
mkdir -p data/uploads data/output data/temp data/wiktextract data/fonts static

echo ""
echo "🚀 启动服务（conda automation 环境）..."
echo "📱 访问地址: http://localhost:8080"
echo "💡 按 Ctrl+C 停止服务"
echo ""

conda run -n automation python api.py
