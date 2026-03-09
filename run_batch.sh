#!/bin/bash

# 批量视频处理脚本
# 用法: ./run_batch.sh
# 会依次处理 input_videos 目录下的所有视频

# 进入脚本所在目录
cd "$(dirname "$0")"

# 视频列表（可以手动修改这里）
VIDEOS=(
    "Epstein files tied to Trump sexual assault allegations released.mp4"
    "How Anthropic Became The First U.S. Company To Be Designated As A Supply Chain Risk.mp4"
    "Iranian strikes hit Dubai as Middle East conflict expands _ 7NEWS.mp4"
)

# 逐个处理视频
for video in "${VIDEOS[@]}"; do
    echo "========================================"
    echo "开始处理视频: $video"
    echo "========================================"
    
    # 修改 config.py 中的 INPUT_VIDEO_PATH
    sed -i '' "s|^INPUT_VIDEO_PATH = \".*\"|INPUT_VIDEO_PATH = \"input_videos/$video\"|" config.py
    
    # 运行 main.py
    python main.py
    
    echo ""
    echo "视频处理完成: $video"
    echo ""
done

echo "========================================"
echo "所有视频处理完成！"
echo "========================================"
