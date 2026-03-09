#!/bin/bash

# 批量视频处理脚本
# 用法: ./run_batch.sh
# 会依次处理配置中的所有视频，每个视频可以指定不同的清晰度

# 进入脚本所在目录
cd "$(dirname "$0")"

# 视频列表
VIDEOS=(
    "Teens arrested after teacher prank turns deadly in Georgia.mp4"
    "A look Iran's weapons being used for strikes in Israel.mp4"
    "Explosive devices thrown at NYC Mayor Zohran Mamdani's residence.mp4"
)

# 清晰度列表（顺序与 VIDEOS 对应）
# 可选值: "1080p" 或 "720p"
RESOLUTIONS=(
    "720p"
    "1080p"
    "1080p"
)

# 获取视频数量
num_videos=${#VIDEOS[@]}

# 逐个处理视频
for ((i=0; i<num_videos; i++)); do
    video="${VIDEOS[$i]}"
    resolution="${RESOLUTIONS[$i]}"
    
    echo "========================================"
    echo "开始处理视频: $video"
    echo "清晰度: $resolution"
    echo "========================================"
    
    # 修改 config.py 中的 INPUT_VIDEO_PATH
    sed -i '' "s|^INPUT_VIDEO_PATH = \".*\"|INPUT_VIDEO_PATH = \"input_videos/$video\"|" config.py
    
    # 修改 config.py 中的 VIDEO_RESOLUTION
    sed -i '' "s|^VIDEO_RESOLUTION = \".*\"|VIDEO_RESOLUTION = \"$resolution\"|" config.py
    
    # 运行 main.py
    python main.py
    
    echo ""
    echo "视频处理完成: $video"
    echo ""
done

echo "========================================"
echo "所有视频处理完成！"
echo "========================================"
