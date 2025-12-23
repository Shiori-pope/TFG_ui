#!/bin/bash
# filepath: e:\codecourse\csv_front\JoyGen\run_joygen.sh
# JoyGen Docker 调用脚本 - 支持训练和推理

set -e  # 遇到错误立即退出

# ========== 配置部分 ==========
IMAGE_NAME="joygen:v1.0"                # Docker 镜像名
WORKSPACE="/app"                        # 容器内工作目录
JOYGEN_DIR="./JoyGen"                   # 宿主机 JoyGen 目录

# ========== 工具函数 ==========

# 获取文件名（不含扩展名）
get_basename() {
    local file_path="$1"
    local basename=$(basename "$file_path")
    echo "${basename%.*}"
}

# 解析 GPU 参数
parse_gpu_arg() {
    local gpu_arg="$1"
    local upper_arg=$(echo "$gpu_arg" | tr '[:lower:]' '[:upper:]')
    
    if [[ "$upper_arg" == "CPU" ]]; then
        echo ""
    elif [[ "$upper_arg" =~ ^GPU[0-9]+$ ]]; then
        local gpu_num=$(echo "$upper_arg" | sed 's/GPU//')
        echo "--gpus device=$gpu_num"
    else
        echo "--gpus device=0"
    fi
}

# 确保目录结构存在
ensure_dirs() {
    mkdir -p "$JOYGEN_DIR/audio"
    mkdir -p "$JOYGEN_DIR/video"
    mkdir -p "$JOYGEN_DIR/results"
    mkdir -p "$JOYGEN_DIR/tmp/preprocessed_dataset"
    mkdir -p "$JOYGEN_DIR/checkpoints"
    echo "[JoyGen] 目录结构已创建"
}

# 检查预训练模型
check_pretrained_models() {
    if [ ! -d "$JOYGEN_DIR/pretrained_models" ]; then
        echo "⚠️  警告：未找到 pretrained_models 目录！"
        echo "    路径: $JOYGEN_DIR/pretrained_models"
        echo "    请确保模型文件已解压到该目录。"
        read -p "是否继续？(y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# ========== 训练功能 ==========
train() {
    local video_path=""
    local gpu_arg="GPU0"
    local epoch="20"
    local batch_size="2"
    local num_workers="4"
    local max_steps="2000"
    local lr="2e-5"
    local min_lr="1e-5"
    local checkpoint_interval="500"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --video_path) video_path="$2"; shift 2 ;;
            --gpu) gpu_arg="$2"; shift 2 ;;
            --epoch) epoch="$2"; shift 2 ;;
            --batch_size) batch_size="$2"; shift 2 ;;
            --num_workers) num_workers="$2"; shift 2 ;;
            --max_steps) max_steps="$2"; shift 2 ;;
            --lr) lr="$2"; shift 2 ;;
            --min_lr) min_lr="$2"; shift 2 ;;
            --checkpoint_interval) checkpoint_interval="$2"; shift 2 ;;
            *) echo "未知参数: $1"; usage; exit 1 ;;
        esac
    done
    
    # 参数校验
    if [ -z "$video_path" ]; then
        echo "错误: 必须指定视频路径 --video_path"
        exit 1
    fi
    
    if [ ! -f "$video_path" ]; then
        echo "错误: 视频文件不存在: $video_path"
        exit 1
    fi
    
    ensure_dirs
    check_pretrained_models
    
    local video_name=$(get_basename "$video_path")
    local gpu_param=$(parse_gpu_arg "$gpu_arg")
    local gpu_id=$(echo "$gpu_arg" | sed 's/GPU//')
    if [ -z "$gpu_id" ]; then gpu_id="0"; fi
    
    # 生成模型目录名（videoName_steps{max_steps}）
    local model_dir_name="${video_name}_steps${max_steps}"
    local model_save_dir="$JOYGEN_DIR/checkpoints/${model_dir_name}"
    mkdir -p "$model_save_dir"
    
    echo "[JoyGen] 开始训练流程..."
    echo "  - 输入视频: $video_path"
    echo "  - 视频名称: $video_name"
    echo "  - 模型保存目录: $model_save_dir"
    echo "  - GPU设置: $gpu_arg (ID: $gpu_id)"
    echo "  - Batch Size: $batch_size"
    echo "  - Max Steps: $max_steps"
    
    # 复制视频到工作目录
    mkdir -p "$JOYGEN_DIR/training_videos"
    cp "$video_path" "$JOYGEN_DIR/training_videos/"
    
    local joygen_abs=$(cd "$JOYGEN_DIR" && pwd)
    
    # 步骤1: 抽帧（预处理数据集）
    echo ""
    echo "[JoyGen] 步骤1/4: 预处理数据集（抽帧、提取特征）"
    docker run --rm \
        $gpu_param \
        --ipc=host \
        --ulimit memlock=-1 \
        --ulimit stack=67108864 \
        -v "$joygen_abs/training_videos:$WORKSPACE/video_dir" \
        -v "$joygen_abs/tmp:$WORKSPACE/tmp" \
        -v "$joygen_abs/pretrained_models:$WORKSPACE/pretrained_models" \
        -e CUDA_VISIBLE_DEVICES=$gpu_id \
        $IMAGE_NAME \
        python -u preprocess_dataset.py \
        --checkpoints_dir ./pretrained_models \
        --name face_recon_feat0.2_augment \
        --epoch=$epoch \
        --use_opengl False \
        --bfm_folder ./pretrained_models/BFM \
        --video_dir video_dir \
        --result_dir ./tmp/preprocessed_dataset
    
    # 步骤2: 打标签
    echo ""
    echo "[JoyGen] 步骤2/4: 生成训练列表（打标签）"
    docker run --rm \
        $gpu_param \
        -v "$joygen_abs/tmp:$WORKSPACE/tmp" \
        -e CUDA_VISIBLE_DEVICES=$gpu_id \
        $IMAGE_NAME \
        python -u preprocess_dataset_extra.py \
        --root_dir ./tmp/preprocessed_dataset \
        --face_list ./tmp/preprocessed_dataset/mylist.txt
    
    # 步骤3: 修改配置参数
    echo ""
    echo "[JoyGen] 步骤3/4: 更新训练配置"
    docker run --rm \
        $IMAGE_NAME \
        python -u update_train_config.py \
        --batch_size $batch_size \
        --num_workers $num_workers \
        --max_steps $max_steps \
        --lr $lr \
        --min_lr $min_lr \
        --checkpoint_interval $checkpoint_interval
    
    # 步骤4: 开始训练
    echo ""
    echo "[JoyGen] 步骤4/4: 开始训练模型"
    echo "  提示: 训练过程可能需要几小时，请耐心等待..."
    echo "  提示: 可以按 Ctrl+C 中断训练"
    docker run --rm \
        --gpus all \
        --ipc=host \
        --ulimit memlock=-1 \
        --ulimit stack=67108864 \
        -v "$joygen_abs/tmp:$WORKSPACE/tmp" \
        -v "$joygen_abs/pretrained_models:$WORKSPACE/pretrained_models" \
        -v "$joygen_abs/checkpoints:$WORKSPACE/checkpoints" \
        -e CUDA_VISIBLE_DEVICES=$gpu_id \
        $IMAGE_NAME \
        accelerate launch \
        --main_process_port 29501 \
        --config_file config/accelerate_config.yaml \
        train_joygen.py
    
    echo ""
    echo "[JoyGen] 训练完成！"
    echo "  ✅ 模型保存位置: $model_save_dir"
    echo "  ✅ 用于推理时请使用: $model_save_dir"
    echo ""
    echo "推理命令示例:"
    echo "  ./run_joygen.sh infer \\"
    echo "    --audio_path <音频路径> \\"
    echo "    --video_path <视频路径> \\"
    echo "    --model_dir $model_save_dir"
    
    # 清理临时文件
    echo ""
    echo "[JoyGen] 清理临时文件..."
    if [ -d "$JOYGEN_DIR/tmp" ]; then
        rm -rf "$JOYGEN_DIR/tmp"
        echo "  已删除: $JOYGEN_DIR/tmp/"
    fi
    echo "[JoyGen] 清理完成！"
}

# ========== 推理功能 ==========
infer() {
    local audio_path=""
    local video_path=""
    local result_dir=""
    local gpu_arg="GPU0"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --audio_path) audio_path="$2"; shift 2 ;;
            --video_path) video_path="$2"; shift 2 ;;
            --result_dir) result_dir="$2"; shift 2 ;;
            --gpu) gpu_arg="$2"; shift 2 ;;
            *) echo "未知参数: $1"; usage; exit 1 ;;
        esac
    done
    
    # 参数校验
    if [ -z "$audio_path" ]; then
        echo "错误: 必须指定音频路径 --audio_path"
        exit 1
    fi
    
    if [ -z "$video_path" ]; then
        echo "错误: 必须指定视频路径 --video_path"
        exit 1
    fi
    
    if [ ! -f "$audio_path" ]; then
        echo "错误: 音频文件不存在: $audio_path"
        exit 1
    fi
    
    if [ ! -f "$video_path" ]; then
        echo "错误: 视频文件不存在: $video_path"
        exit 1
    fi
    
    ensure_dirs
    check_pretrained_models
    
    # 设置默认结果目录
    if [ -z "$result_dir" ]; then
        local audio_name=$(get_basename "$audio_path")
        local video_name=$(get_basename "$video_path")
        result_dir="$JOYGEN_DIR/results/${video_name}_${audio_name}"
    fi
    
    mkdir -p "$result_dir"
    
    local audio_name=$(basename "$audio_path")
    local video_name=$(basename "$video_path")
    local gpu_param=$(parse_gpu_arg "$gpu_arg")
    local gpu_id=$(echo "$gpu_arg" | sed 's/GPU//')
    if [ -z "$gpu_id" ]; then gpu_id="0"; fi
    
    echo "[JoyGen] 开始推理..."
    echo "  - 音频文件: $audio_path"
    echo "  - 视频文件: $video_path"
    echo "  - 结果目录: $result_dir"
    echo "  - GPU设置: $gpu_arg (ID: $gpu_id)"
    
    # 复制文件到工作目录（如果不在目标目录中）
    local audio_abs=$(realpath "$audio_path")
    local video_abs=$(realpath "$video_path")
    local joygen_audio_abs=$(realpath "$JOYGEN_DIR/audio")
    local joygen_video_abs=$(realpath "$JOYGEN_DIR/video")
    
    # 只有当文件不在目标目录时才复制
    if [[ ! "$audio_abs" == "$joygen_audio_abs"* ]]; then
        cp "$audio_path" "$JOYGEN_DIR/audio/"
    fi
    if [[ ! "$video_abs" == "$joygen_video_abs"* ]]; then
        cp "$video_path" "$JOYGEN_DIR/video/"
    fi
    
    # 获取绝对路径
    local joygen_abs=$(cd "$JOYGEN_DIR" && pwd)
    
    # ========== 关键修改：只挂载必要的目录 ========== 
    echo "[JoyGen] 执行推理流水线..."
    docker run --rm \
        $gpu_param \
        --ipc=host \
        --ulimit memlock=-1 \
        --ulimit stack=67108864 \
        -v "$joygen_abs/audio:$WORKSPACE/audio" \
        -v "$joygen_abs/video:$WORKSPACE/video" \
        -v "$joygen_abs/results:$WORKSPACE/results" \
        -v "$joygen_abs/pretrained_models:$WORKSPACE/pretrained_models" \
        -e CUDA_VISIBLE_DEVICES=$gpu_id \
        $IMAGE_NAME \
        bash -c "dos2unix scripts/inference_pipeline.sh 2>/dev/null || sed -i 's/\r$//' scripts/inference_pipeline.sh; bash scripts/inference_pipeline.sh audio/$audio_name video/$video_name results/$(basename "$result_dir")"
    
    echo "[JoyGen] 推理完成！"
    echo "  输出视频位置: $result_dir/"
    
    # 查找生成的视频文件
    if [ -d "$result_dir" ]; then
        local output_files=$(find "$result_dir" -name "*.mp4" 2>/dev/null)
        if [ -n "$output_files" ]; then
            echo "  生成的视频文件:"
            echo "$output_files" | while read -r file; do
                echo "    - $file"
            done
        fi
    fi
}

# ========== 手动推理（分步执行，用于调试） ==========
infer_manual() {
    local audio_path=""
    local video_path=""
    local result_dir=""
    local gpu_arg="GPU0"
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --audio_path) audio_path="$2"; shift 2 ;;
            --video_path) video_path="$2"; shift 2 ;;
            --result_dir) result_dir="$2"; shift 2 ;;
            --gpu) gpu_arg="$2"; shift 2 ;;
            *) echo "未知参数: $1"; usage; exit 1 ;;
        esac
    done
    
    # 参数校验
    if [ -z "$audio_path" ] || [ -z "$video_path" ]; then
        echo "错误: 必须指定音频和视频路径"
        exit 1
    fi
    
    if [ ! -f "$audio_path" ] || [ ! -f "$video_path" ]; then
        echo "错误: 文件不存在"
        exit 1
    fi
    
    ensure_dirs
    check_pretrained_models
    
    if [ -z "$result_dir" ]; then
        local audio_name=$(get_basename "$audio_path")
        local video_name=$(get_basename "$video_path")
        result_dir="$JOYGEN_DIR/results/${video_name}_${audio_name}"
    fi
    
    mkdir -p "$result_dir/a2m"
    mkdir -p "$result_dir/edit_expression"
    mkdir -p "$result_dir/talk"
    
    local audio_name=$(basename "$audio_path")
    local video_name=$(basename "$video_path")
    local audio_basename=$(get_basename "$audio_path")
    local video_basename=$(get_basename "$video_path")
    local gpu_param=$(parse_gpu_arg "$gpu_arg")
    local gpu_id=$(echo "$gpu_arg" | sed 's/GPU//')
    if [ -z "$gpu_id" ]; then gpu_id="0"; fi
    
    # 复制文件（如果不在目标目录中）
    local audio_abs=$(realpath "$audio_path")
    local video_abs=$(realpath "$video_path")
    local joygen_audio_abs=$(realpath "$JOYGEN_DIR/audio")
    local joygen_video_abs=$(realpath "$JOYGEN_DIR/video")
    
    if [[ ! "$audio_abs" == "$joygen_audio_abs"* ]]; then
        cp "$audio_path" "$JOYGEN_DIR/audio/"
    fi
    if [[ ! "$video_abs" == "$joygen_video_abs"* ]]; then
        cp "$video_path" "$JOYGEN_DIR/video/"
    fi
    
    local joygen_abs=$(cd "$JOYGEN_DIR" && pwd)
    
    echo "[JoyGen] 步骤1/3: 音频 → 表情系数"
    docker run --rm \
        $gpu_param \
        --ipc=host \
        --ulimit memlock=-1 \
        --ulimit stack=67108864 \
        -v "$joygen_abs/audio:$WORKSPACE/audio" \
        -v "$joygen_abs/video:$WORKSPACE/video" \
        -v "$joygen_abs/results:$WORKSPACE/results" \
        -v "$joygen_abs/pretrained_models:$WORKSPACE/pretrained_models" \
        -e CUDA_VISIBLE_DEVICES=$gpu_id \
        $IMAGE_NAME \
        python inference_audio2motion.py \
        --a2m_ckpt ./pretrained_models/audio2motion/240210_real3dportrait_orig/audio2secc_vae \
        --hubert_path ./pretrained_models/audio2motion/hubert \
        --drv_aud audio/$audio_name \
        --seed 0 \
        --result_dir results/$(basename "$result_dir")/a2m \
        --exp_file ${audio_basename}.npy
    
    echo "[JoyGen] 步骤2/3: 表情系数 + 视频 → 深度图"
    docker run --rm \
        $gpu_param \
        --ipc=host \
        --ulimit memlock=-1 \
        --ulimit stack=67108864 \
        -v "$joygen_abs/audio:$WORKSPACE/audio" \
        -v "$joygen_abs/video:$WORKSPACE/video" \
        -v "$joygen_abs/results:$WORKSPACE/results" \
        -v "$joygen_abs/pretrained_models:$WORKSPACE/pretrained_models" \
        -e CUDA_VISIBLE_DEVICES=$gpu_id \
        $IMAGE_NAME \
        python -u inference_edit_expression.py \
        --name face_recon_feat0.2_augment \
        --epoch=20 \
        --use_opengl False \
        --checkpoints_dir ./pretrained_models \
        --bfm_folder ./pretrained_models/BFM \
        --infer_video_path video/$video_name \
        --infer_exp_coeff_path results/$(basename "$result_dir")/a2m/${audio_basename}.npy \
        --infer_result_dir results/$(basename "$result_dir")/edit_expression
    
    echo "[JoyGen] 步骤3/3: 深度图 + 音频 → 最终视频"
    docker run --rm \
        $gpu_param \
        --ipc=host \
        --ulimit memlock=-1 \
        --ulimit stack=67108864 \
        -v "$joygen_abs/audio:$WORKSPACE/audio" \
        -v "$joygen_abs/video:$WORKSPACE/video" \
        -v "$joygen_abs/results:$WORKSPACE/results" \
        -v "$joygen_abs/pretrained_models:$WORKSPACE/pretrained_models" \
        -e CUDA_VISIBLE_DEVICES=$gpu_id \
        $IMAGE_NAME \
        python -u inference_joygen.py \
        --unet_model_path pretrained_models/joygen \
        --vae_model_path pretrained_models/sd-vae-ft-mse \
        --intermediate_dir results/$(basename "$result_dir")/edit_expression \
        --audio_path audio/$audio_name \
        --video_path video/$video_name \
        --enable_pose_driven \
        --result_dir results/$(basename "$result_dir")/talk \
        --img_size 256 \
        --gpu_id $gpu_id
    
    echo "[JoyGen] 推理完成！"
    echo "  输出视频: $result_dir/talk/"
}

# ========== 使用说明 ==========
usage() {
    cat << EOF
JoyGen Docker 调用脚本 - 支持训练和推理

训练模式:
    ./run_joygen.sh train \\
        --video_path <视频路径> \\
        [--gpu GPU0] \\
        [--epoch 20] \\
        [--batch_size 2] \\
        [--num_workers 4] \\
        [--max_steps 2000] \\
        [--lr 2e-5] \\
        [--min_lr 1e-5] \\
        [--checkpoint_interval 500]

推理模式（简化版，推荐）:
    ./run_joygen.sh infer \\
        --audio_path <音频路径> \\
        --video_path <视频路径> \\
        [--result_dir <结果目录>] \\
        [--gpu GPU0]

手动推理模式（分步执行，调试用）:
    ./run_joygen.sh infer_manual \\
        --audio_path <音频路径> \\
        --video_path <视频路径> \\
        [--result_dir <结果目录>] \\
        [--gpu GPU0]

示例:
    # 训练
    ./run_joygen.sh train \\
        --video_path ./my_video.mp4 \\
        --gpu GPU0 \\
        --max_steps 1000

    # 推理
    ./run_joygen.sh infer \\
        --audio_path ./demo/xinwen_5s.mp3 \\
        --video_path ./demo/example_5s.mp4 \\
        --gpu GPU0

    # 手动推理（分步调试）
    ./run_joygen.sh infer_manual \\
        --audio_path ./audio.wav \\
        --video_path ./video.mp4 \\
        --result_dir ./my_results \\
        --gpu GPU1

注意:
    - 训练需要高质量人脸视频（建议3-10分钟）
    - 训练需要大显存GPU（建议16GB+）
    - 推理需要同时提供音频和视频文件
    - GPU参数: GPU0, GPU1, GPU2, ... 或 CPU
    - 需要预训练模型在 JoyGen/pretrained_models/ 目录
EOF
}

# ========== 主入口 ==========
case "$1" in
    train) shift; train "$@" ;;
    infer) shift; infer "$@" ;;
    infer_manual) shift; infer_manual "$@" ;;
    *) usage; exit 1 ;;
esac