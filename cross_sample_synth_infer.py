import os
import sys
import shutil
import random
import json
import subprocess
import logging
import time
import uuid
from pathlib import Path

# ===================== 核心配置 =====================
IMAGE_NAME = "joygen:v1.0"
HOST_JOYGEN_DIR = os.path.abspath(".")
DOCKER_WORKDIR = "/app"

# ===================== 初始化目录 =====================
def ensure_joygen_dirs():
    dirs = ["audio", "video", "results", "pretrained_models"]
    for d in dirs:
        p = os.path.join(HOST_JOYGEN_DIR, d)
        os.makedirs(p, exist_ok=True)
    
    if not os.path.exists(os.path.join(HOST_JOYGEN_DIR, "pretrained_models", "audio2motion")):
        print(f"⚠️ 警告: 未在 {HOST_JOYGEN_DIR}/pretrained_models 中发现模型文件！")
        time.sleep(3)

def setup_logger(output_dir):
    log_path = os.path.join(output_dir, "synthesis_log.txt")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def get_valid_videos(input_dir):
    exts = ['.mp4', '.mov', '.avi']
    if not os.path.exists(input_dir): return []
    return [f for f in os.listdir(input_dir) if Path(f).suffix.lower() in exts]

# ===================== Docker 管理 =====================

def start_persistent_container():
    logger = logging.getLogger(__name__)
    container_name = f"joygen_worker_{uuid.uuid4().hex[:6]}"
    logger.info(f"🚀 启动常驻容器: {container_name}")

    cmd = [
        "docker", "run", "-d", "--rm",
        "--gpus", "all",
        "--ipc=host",
        "--ulimit", "memlock=-1",
        "--ulimit", "stack=67108864",
        "--name", container_name,
        "-e", "MAX_JOBS=2", # 依然保留，防止Ninja编译崩溃
        "-v", f"{HOST_JOYGEN_DIR}/audio:{DOCKER_WORKDIR}/audio",
        "-v", f"{HOST_JOYGEN_DIR}/video:{DOCKER_WORKDIR}/video",
        "-v", f"{HOST_JOYGEN_DIR}/results:{DOCKER_WORKDIR}/results",
        "-v", f"{HOST_JOYGEN_DIR}/pretrained_models:{DOCKER_WORKDIR}/pretrained_models",
        "-w", DOCKER_WORKDIR,
        IMAGE_NAME,
        "tail", "-f", "/dev/null"
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        logger.info("✅ 容器已就绪")
        return container_name
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ 容器启动失败: {e}")
        sys.exit(1)

def stop_container(container_name):
    if container_name:
        subprocess.run(["docker", "stop", container_name], check=False, stdout=subprocess.DEVNULL)

# ===================== 核心推理逻辑 (已修复格式问题) =====================

def run_inference_logic(container_name, visual_path, audio_path, task_id):
    logger = logging.getLogger(__name__)

    # 1. 准备文件名
    v_name = Path(visual_path).name
    a_name_raw = Path(audio_path).name # 原始文件名 (可能是 .mp4)
    
    # 结果目录名
    res_dir_name = f"{Path(v_name).stem}_{Path(a_name_raw).stem}_tid{task_id}"
    
    # 2. 文件搬运 (宿主机操作)
    dest_v = os.path.join(HOST_JOYGEN_DIR, "video", v_name)
    dest_a = os.path.join(HOST_JOYGEN_DIR, "audio", a_name_raw)
    
    if os.path.abspath(visual_path) != os.path.abspath(dest_v):
        shutil.copy(visual_path, dest_v)
    if os.path.abspath(audio_path) != os.path.abspath(dest_a):
        shutil.copy(audio_path, dest_a)

    # 3. 构造容器内路径
    c_video_path = f"video/{v_name}"
    c_audio_raw_path = f"audio/{a_name_raw}" # 容器内原始文件路径
    c_res_dir = f"results/{res_dir_name}"
    
    # 【关键修复】定义转换后的 wav 路径
    # 我们将在容器内把 mp4 转成 wav
    a_name_wav = f"{Path(a_name_raw).stem}.wav"
    c_audio_wav_path = f"audio/{a_name_wav}"

    # ---------------------------------------------------------
    # 构造命令链
    # ---------------------------------------------------------

    # Step 0: 格式转换 (MP4 -> WAV 16k)
    # 必须在 step 1 之前执行，否则 infer_audio2motion 会报错
    cmd_extract = (
        f"ffmpeg -i {c_audio_raw_path} "
        f"-vn -acodec pcm_s16le -ar 16000 -ac 1 -y {c_audio_wav_path} "
        f"-loglevel error"
    )

    # Step 1: Audio2Motion (使用 .wav)
    cmd_1 = (
        f"python inference_audio2motion.py "
        f"--a2m_ckpt ./pretrained_models/audio2motion/240210_real3dportrait_orig/audio2secc_vae "
        f"--hubert_path ./pretrained_models/audio2motion/hubert "
        f"--drv_aud {c_audio_wav_path} " # <--- 这里改成 wav
        f"--seed 0 "
        f"--result_dir {c_res_dir}/a2m "
        f"--exp_file {Path(a_name_raw).stem}.npy"
    )

    # Step 2: Edit Expression
    cmd_2 = (
        f"python -u inference_edit_expression.py "
        f"--name face_recon_feat0.2_augment "
        f"--epoch=20 "
        f"--use_opengl False "
        f"--checkpoints_dir ./pretrained_models "
        f"--bfm_folder ./pretrained_models/BFM "
        f"--infer_video_path {c_video_path} "
        f"--infer_exp_coeff_path {c_res_dir}/a2m/{Path(a_name_raw).stem}.npy "
        f"--infer_result_dir {c_res_dir}/edit_expression"
    )

    # Step 3: JoyGen (使用 .wav 作为音频源)
    cmd_3 = (
        f"python -u inference_joygen.py "
        f"--unet_model_path pretrained_models/joygen "
        f"--vae_model_path pretrained_models/sd-vae-ft-mse "
        f"--intermediate_dir {c_res_dir}/edit_expression "
        f"--audio_path {c_audio_wav_path} " # <--- 这里也改成 wav，保证音画同步
        f"--video_path {c_video_path} "
        f"--enable_pose_driven "
        f"--result_dir {c_res_dir}/talk "
        f"--img_size 256 "
        f"--gpu_id 0"
    )

    # 4. 执行
    # 先做 Step 0 (转换)，再做后续推理
    full_cmd = f"set -e && {cmd_extract} && {cmd_1} && {cmd_2} && {cmd_3}"
    
    try:
        subprocess.run(
            ["docker", "exec", container_name, "/bin/bash", "-c", full_cmd],
            check=True
        )
        
        # 返回宿主机结果路径
        host_res_dir = os.path.join(HOST_JOYGEN_DIR, "results", res_dir_name, "talk")
        return host_res_dir
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ 推理步骤失败: {e}")
        return None

# ===================== 结果收集 =====================
def collect_result(host_res_dir, final_output_dir, target_name):
    logger = logging.getLogger(__name__)
    if not host_res_dir or not os.path.exists(host_res_dir): return False

    found_files = []
    for root, _, files in os.walk(host_res_dir):
        for f in files:
            if f.endswith(".mp4"):
                path = os.path.join(root, f)
                found_files.append((path, os.path.getmtime(path)))
    
    if not found_files: return False
    
    latest_video = max(found_files, key=lambda x: x[1])[0]
    target_path = os.path.join(final_output_dir, target_name)
    try:
        shutil.copy(latest_video, target_path)
        logger.info(f"✅ 成功生成: {target_name}")
        return True
    except Exception as e:
        logger.error(f"搬运结果失败: {e}")
        return False

# ===================== 主程序 =====================
def main():
    print("="*60)
    print(" 🧬 JoyGen 修复版 (Auto Audio Extract) ")
    print("="*60)
    
    cwd = os.getcwd()
    def_mid = os.path.join(cwd, "mid")
    def_out = os.path.join(cwd, "out")
    
    print(f"工作区目录: {HOST_JOYGEN_DIR}")
    ensure_joygen_dirs()
    
    inp_in = input(f"1. 输入视频目录 [默认: {def_mid}]: ").strip().replace('"', '')
    inp_dir = os.path.abspath(inp_in if inp_in else def_mid)
    
    out_in = input(f"2. 最终输出目录 [默认: {def_out}]: ").strip().replace('"', '')
    out_dir = os.path.abspath(out_in if out_in else def_out)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    
    try: cnt = int(input("3. 生成对数 N: ").strip() or 1)
    except: cnt = 1

    logger = setup_logger(out_dir)
    videos = get_valid_videos(inp_dir)
    if len(videos) < 2:
        logger.error("视频不足 2 个。")
        return

    cid = None
    try:
        cid = start_persistent_container()
        
        tasks = []
        metadata = []
        
        for i in range(cnt):
            va, vb = random.sample(videos, 2)
            tid = i+1
            
            # Task A: Vis=A, Aud=B
            out_name = f"pair_{tid:03d}_vA_aB.mp4"
            logger.info(f"\n>>> 处理任务 [{tid}-1]: {out_name}")
            # vb 是视频文件，作为音频输入
            res_path = run_inference_logic(cid, os.path.join(inp_dir, va), os.path.join(inp_dir, vb), f"{tid}_1")
            if collect_result(res_path, out_dir, out_name):
                tasks.append(out_name)
            
            # Task B: Vis=B, Aud=A
            out_name = f"pair_{tid:03d}_vB_aA.mp4"
            logger.info(f"\n>>> 处理任务 [{tid}-2]: {out_name}")
            # va 是视频文件，作为音频输入
            res_path = run_inference_logic(cid, os.path.join(inp_dir, vb), os.path.join(inp_dir, va), f"{tid}_2")
            if collect_result(res_path, out_dir, out_name):
                tasks.append(out_name)
                
            metadata.append({"id": tid, "vis": va, "aud": vb})

        with open(os.path.join(out_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=4)
            
    except KeyboardInterrupt:
        logger.warning("用户中断")
    finally:
        stop_container(cid)

if __name__ == "__main__":
    main()