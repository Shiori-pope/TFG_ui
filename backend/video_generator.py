import os
import time
import subprocess
import shutil
import sys

# 确保 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def generate_video(data):
    """
    JoyGen 视频生成
    """
    print("[backend.video_generator] 收到数据：")
    for k, v in data.items():
        print(f"  {k}: {v}")

    try:
        model_dir = data['model_param']
        audio_path = data['ref_audio']
        gpu = data.get('gpu_choice', 'GPU0')
        
        # 检查音频文件是否存在
        if not os.path.exists(audio_path):
            error_msg = f"音频文件不存在: {audio_path}"
            print(f"[backend.video_generator] ❌ {error_msg}")
            raise FileNotFoundError(error_msg)
        
        # 如果使用预训练模型，需要提供参考视频
        # 否则使用训练时的视频
        video_path = data.get('ref_video', './JoyGen/test_data/example_5s.mp4')
        
        # 修复路径分隔符：Windows 反斜杠转 Unix 正斜杠
        audio_path = audio_path.replace('\\', '/')
        video_path = video_path.replace('\\', '/')
        model_dir = model_dir.replace('\\', '/')
        
        print(f"[backend.video_generator] 使用模型: {model_dir}")
        print(f"[backend.video_generator] 音频文件: {audio_path}")
        print(f"[backend.video_generator] 参考视频: {video_path}")
        
        # 根据模型类型选择推理方式
        if 'pretrained_models' in model_dir:
            # 使用预训练模型，调用完整流程
            cmd = [
                "bash", "./JoyGen/run_joygen.sh", "infer",
                "--audio_path", audio_path,
                "--video_path", video_path,
                "--gpu", gpu
            ]
        else:
            # 使用训练后的模型，调用手动推理
            cmd = [
                "bash", "./JoyGen/run_joygen.sh", "infer_manual",
                "--audio_path", audio_path,
                "--video_path", video_path,
                "--gpu", gpu
            ]

        print(f"[backend.video_generator] 执行命令: {' '.join(cmd)}")

        # 执行命令
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=False,  # 不立即抛出异常，先查看输出
            cwd=os.getcwd()
        )
        
        print("[backend.video_generator] 标准输出:", result.stdout)
        print("[backend.video_generator] 标准错误:", result.stderr)
        print(f"[backend.video_generator] 退出码: {result.returncode}")
        
        # 检查是否成功
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else result.stdout
            raise Exception(f"视频生成失败 (退出码 {result.returncode}): {error_msg}")
        
        # 查找生成的视频
        audio_name = os.path.splitext(os.path.basename(audio_path))[0]
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        result_dir = f"./JoyGen/results/{video_name}_{audio_name}/talk"
        
        # 在结果目录中查找生成的视频
        if os.path.exists(result_dir):
            mp4_files = [f for f in os.listdir(result_dir) if f.endswith('.mp4')]
            if mp4_files:
                # 获取最新的视频文件
                source_file = os.path.join(result_dir, mp4_files[0])
                
                # 复制到 static/videos 目录
                output_filename = f"{video_name}_{audio_name}_generated.mp4"
                destination_path = os.path.join("static", "videos", output_filename)
                shutil.copy(source_file, destination_path)
                
                print(f"[backend.video_generator] 视频生成完成: {destination_path}")
                return destination_path
        
        raise Exception(f"未找到生成的视频文件，结果目录: {result_dir}")
        
    except subprocess.CalledProcessError as e:
        print(f"[backend.video_generator] 命令执行失败: {e.stderr}")
        raise Exception(f"视频生成失败: {e.stderr}")
    except Exception as e:
        print(f"[backend.video_generator] 错误: {e}")
        raise
