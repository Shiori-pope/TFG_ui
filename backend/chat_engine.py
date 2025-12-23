import os
import sys
import speech_recognition as sr
from openai import OpenAI
from backend.tts_service import TTSService

# 确保 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

def chat_response(data):
    """
    实时对话系统视频生成逻辑。
    流程: 语音识别 → AI回答 → 语音合成 → 视频生成
    """
    print("[backend.chat_engine] 收到数据：")
    for k, v in data.items():
        print(f"  {k}: {v}")

    # 步骤1: 语音转文字
    input_audio = "./static/audios/input.wav"
    input_text = "./static/text/input.txt"
    
    print("[backend.chat_engine] 步骤1/4: 语音识别...")
    recognized_text = audio_to_text(input_audio, input_text)
    
    # 如果语音识别失败，使用默认文本
    if not recognized_text:
        recognized_text = "你好"
        print(f"[backend.chat_engine] 语音识别失败，使用默认文本: {recognized_text}")
        os.makedirs(os.path.dirname(input_text), exist_ok=True)
        with open(input_text, 'w', encoding='utf-8') as f:
            f.write(recognized_text)

    # 步骤2: 大模型回答
    output_text = "./static/text/output.txt"
    api_key = "sk-9fe3a5fccbdc4678bae47e711a562b2a"
    model = "deepseek-chat"
    
    print("[backend.chat_engine] 步骤2/4: AI生成回答...")
    ai_response = get_ai_response(input_text, output_text, api_key, model)
    
    # 步骤3: 文字转语音（使用 GPT-SoVITS）
    output_audio = "./static/audios/response.wav"
    
    print("[backend.chat_engine] 步骤3/4: 语音合成...")
    # 使用前端传来的参考音频路径
    ref_audio = data.get('ref_audio', 'static/audios/ref_5s.wav')
    tts_success = text_to_speech(ai_response, output_audio, ref_audio)
    
    if not tts_success:
        print("[backend.chat_engine] 警告: 语音合成失败，跳过该步骤")
    
    # 步骤4: 生成视频
    print("[backend.chat_engine] 步骤4/4: 生成视频...")
    
    if tts_success:
        try:
            # 导入视频生成模块
            from backend.video_generator import generate_video
            
            # 构建视频生成参数
            video_data = {
                'model_param': data.get('model_param', './JoyGen/pretrained_models/joygen'),
                'ref_audio': output_audio,
                'ref_video': data.get('ref_video', './JoyGen/test_data/example_15s.mp4'),  # 使用用户选择的视频素材
                'gpu_choice': 'GPU0'
            }
            
            video_path = generate_video(video_data)
            print(f"[backend.chat_engine] 视频生成完成: {video_path}")
            return video_path
            
        except Exception as e:
            print(f"[backend.chat_engine] 视频生成失败: {e}")
            # 返回音频作为备选
            return output_audio
    else:
        print("[backend.chat_engine] 跳过视频生成（TTS失败）")
        return ""

def audio_to_text(input_audio, input_text):
    try:
        # 检查文件是否存在
        if not os.path.exists(input_audio):
            print(f"音频文件不存在: {input_audio}")
            return None
            
        # 初始化识别器
        recognizer = sr.Recognizer()
        
        # 加载音频文件
        with sr.AudioFile(input_audio) as source:
            # 调整环境噪声
            recognizer.adjust_for_ambient_noise(source)
            # 读取音频数据
            audio_data = recognizer.record(source)
            
            print("正在识别语音...")
            
            # 使用Google语音识别
            text = recognizer.recognize_google(audio_data, language='zh-CN')
            
            # 将结果写入文件
            os.makedirs(os.path.dirname(input_text), exist_ok=True)
            with open(input_text, 'w', encoding='utf-8') as f:
                f.write(text)
                
            print(f"语音识别完成！结果已保存到: {input_text}")
            print(f"识别结果: {text}")
            
            return text
            
    except sr.UnknownValueError:
        print("无法识别音频内容")
        return None
    except sr.RequestError as e:
        print(f"语音识别服务错误: {e}")
        return None
    except FileNotFoundError:
        print(f"音频文件不存在: {input_audio}")
        return None
    except Exception as e:
        print(f"发生错误: {e}")
        return None

def get_ai_response(input_text, output_text, api_key, model, retries=3, delay=2):
    """
    使用 DeepSeek API 生成 AI 回答
    
    Args:
        input_text: 输入文本文件路径
        output_text: 输出文本文件路径
        api_key: DeepSeek API key
        model: 模型名称（deepseek-chat）
        retries: 重试次数
        delay: 重试延迟（秒）
    
    Returns:
        str: AI生成的回答文本
    """
    try:
        # 读取输入文本
        with open(input_text, 'r', encoding='utf-8') as file:
            content = file.read().strip()
        
        # 初始化 DeepSeek 客户端
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        # 带重试机制的 API 调用
        for attempt in range(retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是一个语音对话助手。回答要求：1) 使用日常口语，像朋友聊天一样自然；2) 回答简短，控制在30字以内，说话时长不超过15秒；3) 避免书面语、专业术语和长句子；4) 直接回答重点，不要啰嗦。"},
                        {"role": "user", "content": content}
                    ],
                    stream=False,
                    temperature=0.7
                )
                
                output = response.choices[0].message.content
                
                # 保存输出文本
                with open(output_text, 'w', encoding='utf-8') as file:
                    file.write(output if output else "")
                
                print(f"答复已保存到: {output_text}")
                print(f"AI回答: {output}")
                return output if output else ""
                
            except Exception as e:
                print(f"[get_ai_response] API调用失败 (尝试 {attempt + 1}/{retries}): {e}")
                if attempt < retries - 1:
                    import time
                    time.sleep(delay)
                else:
                    # 最后一次失败，返回默认回答
                    default_response = "抱歉，我现在无法回答，请稍后再试。"
                    with open(output_text, 'w', encoding='utf-8') as file:
                        file.write(default_response)
                    return default_response
                    
    except FileNotFoundError:
        print(f"[get_ai_response] 输入文件不存在: {input_text}")
        return ""
    except Exception as e:
        print(f"[get_ai_response] 错误: {e}")
        return ""

def text_to_speech(text, output_path, ref_audio_path=None):
    """
    使用 GPT-SoVITS 进行文字转语音
    
    Args:
        text: 要合成的文字
        output_path: 输出音频路径
        ref_audio_path: 参考音频路径（用于音色克隆）
    
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        tts = TTSService()
        
        # 检查服务是否可用
        if not tts.check_service():
            print("[text_to_speech] GPT-SoVITS 服务未启动，请先启动服务")
            print("[text_to_speech] 启动命令: python GPT-SoVITS-v2pro/api_v2.py")
            return False
        
        # 转换为绝对路径（如果提供了相对路径）
        if ref_audio_path and not os.path.isabs(ref_audio_path):
            ref_audio_path = os.path.abspath(ref_audio_path)
        
        # 调用 TTS 服务
        success = tts.text_to_speech(text, output_path, ref_audio_path=ref_audio_path)
        return success
    except Exception as e:
        print(f"[text_to_speech] 错误: {e}")
        return False