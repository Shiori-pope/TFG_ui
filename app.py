from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sys
import subprocess
import threading
import time
from werkzeug.utils import secure_filename
from backend.video_generator import generate_video
from backend.model_trainer import train_model
from backend.chat_engine import chat_response

# 设置全局 UTF-8 编码
if sys.platform == 'win32':
    import locale
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    # 设置标准输出为 UTF-8
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 支持中文 JSON

# 配置上传文件
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'wav', 'mp3', 'flac'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/audios', exist_ok=True)
os.makedirs('static/videos', exist_ok=True)
os.makedirs('static/text', exist_ok=True)

# ========== GPT-SoVITS 服务自动启动 ==========
tts_process = None

def start_tts_service():
    """后台启动 GPT-SoVITS TTS 服务"""
    global tts_process
    
    # 检查服务是否已经运行
    try:
        import requests
        response = requests.get("http://127.0.0.1:9880", timeout=2)
        print("[TTS] GPT-SoVITS 服务已在运行")
        return
    except:
        pass
    
    print("[TTS] 正在启动 GPT-SoVITS 服务...")
    
    # 获取 GPT-SoVITS 的 Python 环境
    tts_dir = os.path.join(os.getcwd(), "GPT-SoVITS-v2pro")
    python_exe = os.path.join(tts_dir, "runtime", "python.exe")
    
    # 如果没有独立环境，使用当前 Python
    if not os.path.exists(python_exe):
        python_exe = sys.executable
        print(f"[TTS] 使用当前 Python 环境: {python_exe}")
    else:
        print(f"[TTS] 使用独立 Python 环境: {python_exe}")
    
    try:
        # 启动 TTS 服务 - 直接继承当前进程的 stdout/stderr，便于调试
        print(f"[TTS] 执行命令: {python_exe} api_v2.py -a 127.0.0.1 -p 9880")
        print(f"[TTS] 工作目录: {tts_dir}")
        print("[TTS] " + "="*60)
        
        tts_process = subprocess.Popen(
            [python_exe, "api_v2.py", "-a", "127.0.0.1", "-p", "9880"],
            cwd=tts_dir,
            # 不捕获输出，直接显示在控制台
            stdout=None,
            stderr=None,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0  # Windows 下打开新窗口
        )
        
        print(f"[TTS] 进程已启动，PID: {tts_process.pid}")
        print("[TTS] 等待服务就绪...")
        
        # 等待服务启动
        max_wait_time = 60  # 最多等待 60 秒（加载模型需要时间）
        start_time = time.time()
        service_ready = False
        
        while time.time() - start_time < max_wait_time:
            # 检查进程是否还在运行
            if tts_process.poll() is not None:
                print(f"[TTS] ❌ 服务进程已退出，退出码: {tts_process.returncode}")
                print(f"[TTS] 请查看新窗口的错误信息，或手动运行:")
                print(f"[TTS]     cd GPT-SoVITS-v2pro")
                print(f"[TTS]     {python_exe} api_v2.py")
                return
            
            # 检查服务是否可访问
            try:
                import requests
                response = requests.get("http://127.0.0.1:9880", timeout=1)
                service_ready = True
                break
            except:
                elapsed = int(time.time() - start_time)
                if elapsed % 5 == 0 and elapsed > 0:  # 每 5 秒打印一次
                    print(f"[TTS] 等待中... ({elapsed}秒，加载模型中)")
                time.sleep(1)
        
        if service_ready:
            print("[TTS] ✅ GPT-SoVITS 服务启动成功！")
            print("[TTS] 服务地址: http://127.0.0.1:9880")
        else:
            print("[TTS] ⚠️ GPT-SoVITS 服务启动超时（60秒）")
            print("[TTS] 服务可能仍在加载大模型，请稍后访问 http://127.0.0.1:9880 确认")
            print("[TTS] 或查看新打开的控制台窗口了解详细信息")
            
    except Exception as e:
        print(f"[TTS] ❌ 启动 GPT-SoVITS 服务失败: {e}")
        import traceback
        traceback.print_exc()
        print(f"[TTS] 请手动运行: cd GPT-SoVITS-v2pro && python api_v2.py")

# 在后台线程启动 TTS 服务
def init_tts_service():
    tts_thread = threading.Thread(target=start_tts_service, daemon=True)
    tts_thread.start()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 首页
@app.route('/')
def index():
    return render_template('index.html')

# 视频生成界面
@app.route('/video_generation', methods=['GET', 'POST'])
def video_generation():
    if request.method == 'POST':
        try:
            data = {
                "model_name": request.form.get('model_name'),
                "model_param": request.form.get('model_param'),
                "ref_audio": request.form.get('ref_audio'),
                "ref_video": request.form.get('ref_video'),
                "gpu_choice": request.form.get('gpu_choice'),
            }

            video_path = generate_video(data)
            return jsonify({'status': 'success', 'video_path': video_path})
        except Exception as e:
            print(f"[app] 视频生成错误: {e}")
            return jsonify({'status': 'error', 'message': str(e)})

    return render_template('video_generation.html')


# 模型训练界面
@app.route('/model_training', methods=['GET', 'POST'])
def model_training():
    if request.method == 'POST':
        try:
            data = {
                "model_choice": request.form.get('model_choice'),
                "ref_video": request.form.get('ref_video'),
                "gpu_choice": request.form.get('gpu_choice'),
                "custom_params": request.form.get('custom_params')
            }

            model_dir = train_model(data)
            model_dir = "/" + model_dir.replace("\\", "/")

            return jsonify({'status': 'success', 'model_dir': model_dir, 'message': f'训练完成！模型保存在: {model_dir}'})
        except Exception as e:
            print(f"[app] 训练错误: {e}")
            return jsonify({'status': 'error', 'message': str(e)})

    return render_template('model_training.html')


# 实时对话系统界面
@app.route('/chat_system', methods=['GET', 'POST'])
def chat_system():
    if request.method == 'POST':
        try:
            data = {
                "model_name": request.form.get('model_name'),
                "model_param": request.form.get('model_param'),
                "ref_video": request.form.get('ref_video'),  # 添加视频素材参数
                "ref_audio": request.form.get('ref_audio'),  # 添加参考音频参数
            }

            video_path = chat_response(data)
            video_path = "/" + video_path.replace("\\", "/")

            return jsonify({'status': 'success', 'video_path': video_path})
        except Exception as e:
            print(f"[app] 对话系统错误: {e}")
            return jsonify({'status': 'error', 'message': str(e)})

    return render_template('chat_system.html')

@app.route('/save_audio', methods=['POST'])
def save_audio():
    if 'audio' not in request.files:
        return jsonify({'status': 'error', 'message': '没有音频文件'})
    
    audio_file = request.files['audio']
    if audio_file.filename == '':
        return jsonify({'status': 'error', 'message': '没有选择文件'})
    
    try:
        # 确保目录存在
        os.makedirs('./static/audios', exist_ok=True)
        
        # 先保存为临时文件
        temp_path = './static/audios/temp_input.webm'
        audio_file.save(temp_path)
        
        # 使用 pydub 转换为 WAV格式
        from pydub import AudioSegment
        audio = AudioSegment.from_file(temp_path)
        output_path = './static/audios/input.wav'
        audio.export(output_path, format='wav')
        
        # 删除临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        print(f"[音频保存] 成功转换为 WAV: {output_path}")
        return jsonify({'status': 'success', 'message': '音频保存成功'})
        
    except ImportError:
        # 如果没有 pydub，直接保存（可能失败）
        print("[音频保存] 警告: pydub 未安装，直接保存文件")
        output_path = './static/audios/input.wav'
        audio_file.save(output_path)
        return jsonify({'status': 'success', 'message': '音频保存成功'})
    except Exception as e:
        print(f"[音频保存] 错误: {e}")
        return jsonify({'status': 'error', 'message': f'保存失败: {str(e)}'})

# 文件上传接口
@app.route('/upload_file', methods=['POST'])
def upload_file():
    """
    通用文件上传接口
    支持视频、音频文件上传
    """
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': '没有文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': '没有选择文件'})
    
    if file and allowed_file(file.filename):
        # 获取原始文件名和扩展名
        original_filename = file.filename
        file_ext = os.path.splitext(original_filename)[1].lower()
        
        # 使用时间戳生成唯一文件名，保持原始扩展名
        import time
        timestamp = int(time.time() * 1000)  # 毫秒级时间戳
        filename = f"{timestamp}{file_ext}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # 返回 Unix 风格路径（使用正斜杠）
        filepath_unix = filepath.replace('\\', '/')
        
        print(f"[文件上传] 原始文件名: {original_filename}")
        print(f"[文件上传] 保存为: {filepath_unix}")
        
        return jsonify({
            'status': 'success', 
            'message': '文件上传成功',
            'filepath': filepath_unix,
            'original_name': original_filename
        })
    else:
        return jsonify({'status': 'error', 'message': '不支持的文件类型'})

# 获取上传文件
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    # 启动 TTS 服务
    print("=" * 60)
    print("正在初始化服务...")
    print("=" * 60)
    init_tts_service()
    
    print("\n" + "=" * 60)
    print("Flask 应用启动成功！")
    print("访问地址: http://127.0.0.1:5001")
    print("=" * 60 + "\n")
    
    app.run(debug=True, port=5001, use_reloader=False)  # use_reloader=False 避免重复启动 TTS
