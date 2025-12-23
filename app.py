from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sys
import subprocess
import threading
import time
import uuid
import json
from werkzeug.utils import secure_filename
from backend.video_generator import generate_video
from backend.model_trainer import train_model
from backend.chat_engine import chat_response
from backend.progress_tracker import tracker

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
            # 检查是否为文本直接输入（跳过语音识别）
            text_input = request.form.get('text_input')
            
            if text_input:
                # 直接文本输入模式
                print(f"[chat_system] 收到文本输入: {text_input}")
                
                # 保存文本到文件
                os.makedirs('./static/text', exist_ok=True)
                input_text_path = './static/text/input.txt'
                with open(input_text_path, 'w', encoding='utf-8') as f:
                    f.write(text_input)
                
                # 构建数据
                data = {
                    "text_input": text_input,  # 直接传递文本，跳过语音识别
                    "model_param": request.form.get('model_param'),
                    "ref_video": request.form.get('ref_video'),
                    "ref_audio": request.form.get('ref_audio'),
                    "audio_only": request.form.get('audio_only', 'false') == 'true',
                }
                
                result_path, ai_text = chat_response(data)
                result_path = "/" + result_path.replace("\\", "/")
                
                # 返回结果
                if data.get('audio_only', False):
                    return jsonify({'status': 'success', 'audio_path': result_path, 'user_text': text_input})
                else:
                    return jsonify({'status': 'success', 'video_path': result_path, 'user_text': text_input})
            
            # 语音输入模式
            # 先处理音频文件（如果有）
            if 'audio' in request.files:
                audio_file = request.files['audio']
                if audio_file and audio_file.filename:
                    print(f"[chat_system] 收到音频文件: {audio_file.filename}")
                    
                    # 确保目录存在
                    os.makedirs('./static/audios', exist_ok=True)
                    
                    # 保存为临时文件
                    temp_path = './static/audios/temp_input.webm'
                    audio_file.save(temp_path)
                    
                    # 转换为 WAV 格式
                    try:
                        from pydub import AudioSegment
                        audio = AudioSegment.from_file(temp_path)
                        output_path = './static/audios/input.wav'
                        audio.export(output_path, format='wav')
                        
                        # 删除临时文件
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        
                        print(f"[chat_system] ✅ 音频已保存并转换: {output_path}")
                    except Exception as e:
                        print(f"[chat_system] ⚠️ 音频转换失败: {e}")
                        # 尝试直接保存
                        output_path = './static/audios/input.wav'
                        audio_file.seek(0)  # 重置文件指针
                        audio_file.save(output_path)
            
            data = {
                "model_name": request.form.get('model_name'),
                "model_param": request.form.get('model_param'),
                "ref_video": request.form.get('ref_video'),  # 添加视频素材参数
                "ref_audio": request.form.get('ref_audio'),  # 添加参考音频参数
                "audio_only": request.form.get('audio_only', 'false') == 'true',  # 纯语音模式
            }

            result_path, recognized_text = chat_response(data)
            result_path = "/" + result_path.replace("\\", "/")
            
            # 根据audio_only模式返回不同的字段
            if data.get('audio_only', False):
                return jsonify({'status': 'success', 'audio_path': result_path, 'user_text': recognized_text})
            else:
                return jsonify({'status': 'success', 'video_path': result_path, 'user_text': recognized_text})
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


# ========== 进度追踪 API ==========
@app.route('/api/progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    """获取任务进度"""
    task_info = tracker.get_task_info(task_id)
    if not task_info:
        return jsonify({'status': 'error', 'message': '任务不存在'})
    
    return jsonify({
        'status': 'success',
        'task': {
            'id': task_id,
            'type': task_info['type'],
            'status': task_info['status'],
            'progress': task_info['progress'],
            'current_step': task_info['current_step'],
            'total_steps': task_info['total_steps'],
            'message': task_info['message'],
            'details': task_info['details'],
            'elapsed_time': time.time() - task_info['start_time']
        }
    })


# ========== 文本转视频 API ==========
@app.route('/api/text_to_video', methods=['POST'])
def text_to_video():
    """文本直接转视频（跳过语音识别）"""
    try:
        data = request.get_json()
        text_input = data.get('text', '').strip()
        
        if not text_input:
            return jsonify({'status': 'error', 'message': '文本内容不能为空'})
        
        # 生成任务 ID
        task_id = str(uuid.uuid4())
        
        # 创建进度追踪任务
        tracker.create_task(task_id, 'text_to_video', total_steps=3)
        
        # 后台执行文本转视频任务
        def run_text_to_video():
            try:
                print(f"[text_to_video] 开始处理任务 {task_id}")
                tracker.update_progress(task_id, 1, '步骤 1/3: 保存文本...')
                
                # 1. 保存文本到文件（使用时间戳避免缓存）
                import time
                timestamp = int(time.time() * 1000)
                input_text_path = f'./static/text/input_{timestamp}.txt'
                os.makedirs(os.path.dirname(input_text_path), exist_ok=True)
                with open(input_text_path, 'w', encoding='utf-8') as f:
                    f.write(text_input)
                print(f"[text_to_video] 文本已保存: {text_input}")
                
                tracker.update_progress(task_id, 2, '步骤 2/3: AI 生成回答...')
                
                # 2. AI 生成回答
                from backend.chat_engine import get_ai_response
                output_text_path = f'./static/text/output_{timestamp}.txt'
                api_key = data.get('api_key', 'sk-9fe3a5fccbdc4678bae47e711a562b2a')
                model = data.get('model', 'deepseek-chat')
                character_name = data.get('character_name')
                character_personality = data.get('character_personality')
                
                print(f"[text_to_video] 调用AI生成回答...")
                if character_name:
                    print(f"[text_to_video] 使用角色: {character_name}")
                ai_response = get_ai_response(input_text_path, output_text_path, api_key, model, character_name, character_personality)
                print(f"[text_to_video] AI回答: {ai_response}")
                
                # 检查是否为纯语音模式
                audio_only = data.get('audio_only', False)
                
                # 根据模式显示不同的进度消息
                if audio_only:
                    tracker.update_progress(task_id, 3, '步骤 3/3: 合成音频...')
                else:
                    tracker.update_progress(task_id, 3, '步骤 3/3: 生成视频...')
                
                # 3. TTS + 视频生成
                from backend.tts_service import TTSService
                from backend.video_generator import generate_video
                
                # 使用时间戳创建唯一文件名
                output_audio = f'./static/audios/response_{timestamp}.wav'
                ref_audio = data.get('ref_audio', 'static/audios/ref_5s.wav')
                
                print(f"[text_to_video] 调用TTS服务, 参考音频: {ref_audio}")
                
                # 使用 TTSService（会自动加载配置文件）
                tts = TTSService()
                tts_success = tts.text_to_speech(ai_response, output_audio, ref_audio_path=ref_audio)
                
                if not tts_success:
                    error_msg = 'TTS 生成失败，请检查GPT-SoVITS服务是否启动'
                    print(f"[text_to_video] ❌ {error_msg}")
                    tracker.complete_task(task_id, False, error_msg)
                    return
                
                print(f"[text_to_video] TTS成功")
                
                if audio_only:
                    # 纯语音模式：只生成语音，不生成视频
                    print(f"[text_to_video] 🎤 纯语音模式，跳过视频生成")
                    # 返回完整路径信息，前端可以直接使用
                    tracker.complete_task(task_id, True, f'语音生成完成: {output_audio}')
                else:
                    # 视频模式：继续生成视频
                    print(f"[text_to_video] 开始生成视频...")
                    
                    # 4. 生成视频
                    video_data = {
                        'model_name': data.get('model_name', 'pretrained_joygen'),
                        'model_param': data.get('model_param', './JoyGen/pretrained_models/JoyGen'),
                        'ref_audio': output_audio,
                        'ref_video': data.get('ref_video', './JoyGen/test_data/example_5s.mp4'),
                        'gpu_choice': data.get('gpu_choice', 'GPU0')
                    }
                    
                    print(f"[text_to_video] 调用视频生成...")
                    video_path = generate_video(video_data)
                    print(f"[text_to_video] ✅ 视频生成成功: {video_path}")
                    
                    tracker.complete_task(task_id, True, f'视频生成完成: {video_path}')
                
            except Exception as e:
                error_msg = f'错误: {str(e)}'
                print(f"[text_to_video] ❌ {error_msg}")
                import traceback
                traceback.print_exc()
                tracker.complete_task(task_id, False, error_msg)
        
        # 启动后台线程
        thread = threading.Thread(target=run_text_to_video, daemon=True)
        thread.start()
        
        return jsonify({
            'status': 'success',
            'task_id': task_id,
            'message': '任务已创建，请通过 task_id 查询进度'
        })
        
    except Exception as e:
        print(f"[文本转视频] 错误: {e}")
        return jsonify({'status': 'error', 'message': str(e)})


# ========== 角色配置API ==========
@app.route('/config/characters.json')
def get_characters_config():
    """返回角色配置JSON"""
    try:
        config_path = os.path.join('config', 'characters.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return jsonify(config)
        else:
            # 返回默认配置
            return jsonify({
                "characters": [
                    {
                        "id": "xiaoya",
                        "name": "小雅",
                        "avatar": "🌸",
                        "description": "温柔 · 甜美",
                        "gender": "female",
                        "ref_audio": "static/audios/voice_cute.wav",
                        "ref_audio_text": "你好，我是小雅",
                        "ref_video": "./JoyGen/test_data/example_15s.mp4",
                        "model_path": "./JoyGen/pretrained_models/joygen"
                    }
                ],
                "settings": {
                    "default_character": "xiaoya"
                }
            })
    except Exception as e:
        print(f"[配置] 加载角色配置失败: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # 启动 TTS 服务
    print("=" * 60)
    print("正在初始化服务...")
    print("=" * 60)
    init_tts_service()
    
    # 获取本机IP地址
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print("\n" + "=" * 60)
    print("Flask 应用启动成功！")
    print("=" * 60)
    print(f"本地访问: http://127.0.0.1:5001")
    print(f"局域网访问: http://{local_ip}:5001")
    print(f"公网访问: http://<你的公网IP>:5001")
    print("=" * 60)
    print("⚠️ 注意事项:")
    print("  1. 确保防火墙已开放 5001 端口")
    print("  2. 如需公网访问，请在路由器配置端口转发")
    print("  3. 生产环境建议使用 Nginx + HTTPS")
    print("=" * 60 + "\n")
    
    # 绑定到 0.0.0.0 以允许外部访问
    app.run(host='0.0.0.0', debug=True, port=5001, use_reloader=False)
