import os
import sys
import subprocess
import logging
import random
import argparse
from pathlib import Path

# ==============================================================================
# 第一部分：容器内工作逻辑 (Worker Mode) - 保持不变
# ==============================================================================
def run_worker_logic():
    # --- 配置区 ---
    INPUT_DIR = "/data/input"
    OUTPUT_DIR = "/data/output"
    TARGET_FRAGMENTS = 50
    FRAGMENT_DURATION = 10
    MIN_FRAG_PER_VIDEO = 5
    VIDEO_EXT = [".mp4", ".mov", ".mkv", ".avi"]
    
    # --- 初始化日志 ---
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - [Docker] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
    logger = logging.getLogger()

    # --- 工具函数 ---
    def get_duration(path):
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path]
            return float(subprocess.check_output(cmd).strip())
        except: return 0.0

    def cut_video(in_path, start, out_path):
        """
        核心修改：强制重编码并缩放到 256x256
        """
        try:
            cmd = [
                "ffmpeg", "-y",
                "-hide_banner", "-loglevel", "error",
                "-ss", str(start),                # 起始时间
                "-i", in_path,                    # 输入
                "-t", str(FRAGMENT_DURATION),     # 持续时间
                "-vf", "scale=256:256,setsar=1",  # 缩放
                "-c:v", "libx264",                # 必须重编码
                "-c:a", "aac",                    # 音频编码
                "-preset", "fast",                # 编码速度
                out_path
            ]
            
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            logger.error(f"❌ ffmpeg 处理失败: {Path(out_path).name}")
            return False
        except Exception as e:
            logger.error(f"❌ 未知错误 {Path(out_path).name}: {e}")
            return False

    # --- 主逻辑 ---
    logger.info(">>> 开始处理 (目标分辨率: 256x256)...")
    
    # 清理旧文件
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith("fragment_"): os.remove(os.path.join(OUTPUT_DIR, f))

    # 1. 扫描视频
    videos = []
    if os.path.exists(INPUT_DIR):
        for f in os.listdir(INPUT_DIR):
            p = os.path.join(INPUT_DIR, f)
            if Path(p).suffix.lower() in VIDEO_EXT:
                dur = get_duration(p)
                if dur >= MIN_FRAG_PER_VIDEO * FRAGMENT_DURATION:
                    videos.append((p, dur))
    
    if len(videos) < 8:
        logger.error(f"❌ 有效视频不足！需要至少8个时长>{MIN_FRAG_PER_VIDEO*FRAGMENT_DURATION}s的视频。当前找到: {len(videos)}个")
        sys.exit(1)
    
    videos = videos[:8] # 取前8个

    # 2. 分配片段数
    counts = [MIN_FRAG_PER_VIDEO] * 8
    for _ in range(TARGET_FRAGMENTS - sum(counts)): counts[random.randint(0, 7)] += 1

    # 3. 执行切割
    total_ok = 0
    frag_idx = 1
    for i, (v_path, v_dur) in enumerate(videos):
        logger.info(f"正在处理视频 [{i+1}/8]: {Path(v_path).name} (计划切割 {counts[i]} 个)")
        
        # 生成随机时间点
        starts = []
        retry = 0
        while len(starts) < counts[i] and retry < 100:
            s = round(random.uniform(0, v_dur - FRAGMENT_DURATION), 2)
            if not any(abs(s - exist) < FRAGMENT_DURATION for exist in starts):
                starts.append(s)
            retry += 1
            
        for s in starts:
            out_name = os.path.join(OUTPUT_DIR, f"fragment_{frag_idx:02d}.mp4")
            if cut_video(v_path, s, out_name):
                total_ok += 1
                frag_idx += 1
    
    logger.info(f"🎉 处理完成！成功生成: {total_ok}/{TARGET_FRAGMENTS}")

# ==============================================================================
# 第二部分：本地启动逻辑 (Host Mode) - 已修改
# ==============================================================================
def run_host_logic():
    # 1. 设置命令行参数解析
    parser = argparse.ArgumentParser(description="Docker 视频处理启动器")
    
    # 定义参数及默认值
    parser.add_argument("-i", "--input", default="testdata", help="本地输入目录 (默认: ./testdata)")
    parser.add_argument("-o", "--output", default="mid", help="本地输出目录 (默认: ./mid)")
    parser.add_argument("-img", "--image", default="joygen:v1.0", help="Docker 镜像名称 (默认: joygen:v1.0)")

    args = parser.parse_args()

    # 2. 路径处理（转换为绝对路径）
    # os.getcwd() 获取当前脚本运行目录
    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)
    image_name = args.image
    
    # 确保输出目录存在（创建 mid 文件夹）
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    print("\n⚡ 极速视频切割启动器 (CLI版) ⚡")
    print("-" * 50)
    print(f"Docker 镜像: {image_name}")
    print(f"输入目录   : {input_dir}")
    print(f"输出目录   : {output_dir}")
    print("-" * 50)

    # 3. 校验与创建
    if not os.path.exists(input_dir):
        print(f"❌ 错误: 输入目录不存在: {input_dir}")
        print(f"   请创建 '{os.path.basename(input_dir)}' 文件夹并放入视频，或使用 -i 指定路径。")
        return

    # 4. 构造命令
    current_script = os.path.abspath(sys.argv[0])
    
    print(f"🚀 正在启动 Docker 任务...")
    
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{input_dir}:/data/input",
        "-v", f"{output_dir}:/data/output",
        "-v", f"{current_script}:/app/main.py",
        "-e", "RUN_MODE=WORKER",
        image_name,
        "python", "/app/main.py"
    ]

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print("\n❌ 运行失败！请检查镜像是否正确或 Docker 是否运行。")
        sys.exit(1)
    except FileNotFoundError:
        print("\n❌ 未找到 docker 命令，请确保已安装 Docker。")
        sys.exit(1)

if __name__ == "__main__":
    # 通过环境变量判断是 Docker 内部还是宿主机
    if os.getenv("RUN_MODE") == "WORKER":
        run_worker_logic()
    else:
        run_host_logic()