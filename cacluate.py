import os
import subprocess

def run_docker_evaluation():
    # 1. 获取当前工作目录路径
    current_dir = os.getcwd()
    
    # 定义宿主机路径
    mid_dir = os.path.join(current_dir, "mid")
    out_dir = os.path.join(current_dir, "out")
    res_dir = os.path.join(current_dir, "analysis")

    # 确保宿主机分析目录存在
    if not os.path.exists(res_dir):
        os.makedirs(res_dir)

    # 2. 准备 Docker 命令
    image_name = "digital-human-eval:v4"
    
    docker_cmd = [
        "docker", "run", "--rm", 
        "--gpus", "all",
        "--ipc=host",
        "-v", f"{mid_dir}:/workspace/data/original_videos",
        "-v", f"{out_dir}:/workspace/data/generated_videos",
        "-v", f"{res_dir}:/workspace/results",
        image_name
    ]

    # 3. 容器内指令逻辑：
    # a. 创建必要的目录和软链接
    # b. 运行评估脚本 (结果会存入 /root/eval/output/)
    # c. 将 output 中的所有文件移动到挂载的 results 目录
    inner_cmd = (
        "mkdir -p /root && ln -sf /workspace /root/eval && " # 路径修复
        "mkdir -p /workspace/output && "                    # 确保输出目录存在
        "python LSE.py && "                                # 执行 LSE
        "python FID.py && "                                # 执行 FID
        "echo '🚚 正在将结果从 /root/eval/output/ 导出到宿主机...' && "
        "mv /workspace/output/* /workspace/results/ 2>/dev/null" # 移动结果到挂载点
    )
    
    docker_cmd.extend(["bash", "-c", inner_cmd])

    print("🚀 启动自动化评估流程...")
    print(f"📍 原始视频: {mid_dir}")
    print(f"📍 生成视频: {out_dir}")
    print(f"📊 最终结果将保存在: {res_dir}")
    print("-" * 50)

    try:
        subprocess.run(docker_cmd, check=True)
        print("-" * 50)
        print("✅ 评估圆满完成！")
        print(f"📁 请在宿主机的 '{res_dir}' 文件夹查看 all_scores.txt 和 score_distribution.png")
    except subprocess.CalledProcessError as e:
        print(f"❌ 运行失败，请检查上方容器日志输出。")

if __name__ == "__main__":
    run_docker_evaluation()