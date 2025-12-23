import subprocess
import os
import time
import sys

# 确保 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def train_model(data):
    """
    JoyGen 模型训练
    """
    print("[backend.model_trainer] 收到数据：")
    for k, v in data.items():
        print(f"  {k}: {v}")
    
    video_path = data['ref_video']
    # 修复路径分隔符
    video_path = video_path.replace('\\', '/')
    
    print(f"输入视频：{video_path}")

    print("[backend.model_trainer] 开始训练 JoyGen 模型...")

    try:
        # 构建 JoyGen 训练命令
        max_steps = data.get('custom_params', '5000')  # 默认 5000 步
        cmd = [
            "bash", "./run_joygen.sh", "train",
            "--video_path", video_path,
            "--gpu", data['gpu_choice'],
            "--max_steps", str(max_steps),
            "--batch_size", "2"
        ]
        
        print(f"[backend.model_trainer] 执行命令: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            check=False,  # 不立即抛出异常，先查看输出
            cwd=os.getcwd()
        )
        
        print("[backend.model_trainer] 训练输出:", result.stdout)
        print("[backend.model_trainer] 错误输出:", result.stderr)
        print(f"[backend.model_trainer] 退出码: {result.returncode}")
        
        # 检查是否成功
        if result.returncode != 0:
            error_msg = result.stderr if result.stderr else result.stdout
            raise Exception(f"训练失败 (退出码 {result.returncode}): {error_msg}")
        
        # 生成模型目录名称
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        model_dir = f"./JoyGen/checkpoints/{video_name}_steps{max_steps}"
        print(f"[backend.model_trainer] 训练完成！模型保存在: {model_dir}")
        
        return model_dir
            
    except subprocess.CalledProcessError as e:
        print(f"[backend.model_trainer] 训练失败: {e.stderr}")
        raise Exception(f"训练失败: {e.stderr}")
    except FileNotFoundError:
        print("[backend.model_trainer] 错误: 找不到训练脚本")
        raise Exception("找不到训练脚本 run_joygen.sh")
    except Exception as e:
        print(f"[backend.model_trainer] 训练错误: {e}")
        raise
