#!/bin/bash
# LinguaLearn Web Server 启动脚本
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

# 创建必要目录（统一迁移到 data/，主站与 AI Tutor 共用）
mkdir -p \
  data/uploads \
  data/output \
  data/temp \
  data/wiktextract \
  data/fonts \
  data/lesson_plans \
  data/fillers \
  data/voices \
  static

echo ""
echo "🚀 启动服务..."
echo "📱 访问地址: http://localhost:8080"
echo "🧠 AI Tutor 模型服务: FunASR/CosyVoice 将随主服务自动拉起（本机地址时）"
echo "💡 按 Ctrl+C 停止服务"
echo ""

if [ -n "${LINGUA_CONDA_ENV:-}" ]; then
  echo "🐍 使用 Conda 环境: ${LINGUA_CONDA_ENV}"
  AUTO_START_MODEL_SERVICES="${AUTO_START_MODEL_SERVICES:-true}" \
  conda run -n "${LINGUA_CONDA_ENV}" python api.py
else
  echo "🐍 使用当前 Python: $(command -v python)"
  AUTO_START_MODEL_SERVICES="${AUTO_START_MODEL_SERVICES:-true}" \
  python api.py
fi
