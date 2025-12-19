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

    # 使用时间戳创建唯一文件名，避免缓存
    import time
    timestamp = int(time.time() * 1000)
    input_text = f"./static/text/input_{timestamp}.txt"
    
    # 步骤1: 语音转文字（如果提供了text_input则跳过）
    if 'text_input' in data and data['text_input']:
        # 直接使用提供的文本，跳过语音识别
        recognized_text = data['text_input']
        print(f"[backend.chat_engine] 使用直接输入的文本: {recognized_text}")
        
        # 保存文本到文件供AI使用
        os.makedirs(os.path.dirname(input_text), exist_ok=True)
        with open(input_text, 'w', encoding='utf-8') as f:
            f.write(recognized_text)
    else:
        # 语音识别模式
        input_audio = "./static/audios/input.wav"
        
        # 清理旧的识别结果，避免读取缓存
        if os.path.exists(input_text):
            os.remove(input_text)
            print(f"[backend.chat_engine] 已清理旧的识别结果")
        
        print("[backend.chat_engine] 步骤1/4: 语音识别...")
        recognized_text = audio_to_text(input_audio, input_text)
        
        # 如果语音识别失败，抛出错误
        if not recognized_text:
            error_msg = "语音识别失败：无法识别音频内容，请确保录音清晰或使用文本输入模式"
            print(f"[backend.chat_engine] {error_msg}")
            raise Exception(error_msg)

    # 步骤2: 大模型回答
    output_text = f"./static/text/output_{timestamp}.txt"
    api_key = "sk-9fe3a5fccbdc4678bae47e711a562b2a"
    model = "deepseek-chat"
    
    # 获取角色信息
    character_name = data.get('character_name')
    character_personality = data.get('character_personality')
    
    print("[backend.chat_engine] 步骤2/4: AI生成回答...")
    if character_name:
        print(f"[backend.chat_engine] 使用角色: {character_name}")
    ai_response = get_ai_response(input_text, output_text, api_key, model, character_name, character_personality)
    
    # 步骤3: 文字转语音（使用 GPT-SoVITS）
    # 使用时间戳创建唯一文件名，避免文件覆盖
    output_audio = f"./static/audios/response_{timestamp}.wav"
    
    print("[backend.chat_engine] 步骤3/4: 语音合成...")
    # 使用前端传来的参考音频路径
    ref_audio = data.get('ref_audio', 'static/audios/ref_5s.wav')
    
    # 使用 TTSService（会自动从配置文件加载 prompt_text）
    from backend.tts_service import TTSService
    tts = TTSService()
    tts_success = tts.text_to_speech(ai_response, output_audio, ref_audio_path=ref_audio)
    
    if not tts_success:
        print("[backend.chat_engine] 警告: 语音合成失败，跳过该步骤")
    
    # 检查是否为纯语音模式
    audio_only = data.get('audio_only', False)
    
    if audio_only:
        # 纯语音模式：只返回音频，不生成视频
        print("[backend.chat_engine] 🎤 纯语音模式，跳过视频生成")
        return output_audio, recognized_text
    
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
            return video_path, recognized_text
            
        except Exception as e:
            print(f"[backend.chat_engine] 视频生成失败: {e}")
            # 返回音频作为备选
            return output_audio, recognized_text
    else:
        print("[backend.chat_engine] 跳过视频生成（TTS失败）")
        return "", recognized_text

def audio_to_text(input_audio, input_text):
    try:
        # 检查文件是否存在
        if not os.path.exists(input_audio):
            print(f"❌ 音频文件不存在: {input_audio}")
            return None
        
        # 检查文件大小和修改时间
        file_size = os.path.getsize(input_audio)
        file_mtime = os.path.getmtime(input_audio)
        from datetime import datetime
        file_time = datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"📁 音频文件信息:")
        print(f"   路径: {input_audio}")
        print(f"   大小: {file_size} bytes")
        print(f"   修改时间: {file_time}")
        
        if file_size < 1000:
            print(f"⚠️ 警告: 音频文件太小 ({file_size} bytes)，可能无法识别")
            
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
                
            print(f"✅ 语音识别完成！结果已保存到: {input_text}")
            print(f"📝 识别结果: {text}")
            
            return text
            
    except sr.UnknownValueError:
        print("❌ 无法识别音频内容 - 可能原因：")
        print("   1. 录音时间太短")
        print("   2. 背景噪音过大")
        print("   3. 未检测到语音信号")
        print("   建议：请使用文本输入模式")
        return None
    except sr.RequestError as e:
        print(f"❌ 语音识别服务错误: {e}")
        print("   可能原因：网络连接问题或Google服务不可用")
        print("   建议：检查网络连接或使用文本输入模式")
        return None
    except FileNotFoundError:
        print(f"音频文件不存在: {input_audio}")
        return None
    except Exception as e:
        print(f"发生错误: {e}")
        return None

def get_ai_response(input_text, output_text, api_key, model, character_name=None, character_personality=None, retries=3, delay=2):
    """
    使用 DeepSeek API 生成 AI 回答
    
    Args:
        input_text: 输入文本文件路径
        output_text: 输出文本文件路径
        api_key: DeepSeek API key
        model: 模型名称（deepseek-chat）
        character_name: 角色名字（例如：小雅、小晨）
        character_personality: 角色性格描述
        retries: 重试次数
        delay: 重试延迟（秒）
    
    Returns:
        str: AI生成的回答文本
    """
    try:
        # 读取输入文本
        print(f"[get_ai_response] 读取输入文件: {input_text}")
        with open(input_text, 'r', encoding='utf-8') as file:
            content = file.read().strip()
        
        print(f"[get_ai_response] 输入内容: {content}")
        
        if not content:
            print("[get_ai_response] 警告: 输入内容为空")
            return "请问有什么可以帮助您的？"
        
        # 初始化 DeepSeek 客户端
        print(f"[get_ai_response] 初始化API客户端, model={model}")
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=30.0  # 设置30秒超时
        )
        
        # 带重试机制的 API 调用
        for attempt in range(retries):
            try:
                print(f"[get_ai_response] 开始调用API (尝试 {attempt + 1}/{retries})...")
                
                # 构建系统提示词
                import time
                from datetime import datetime
                current_time = datetime.now().strftime("%H:%M:%S")
                random_seed = int(time.time() * 1000) % 1000
                
                if character_name and character_personality:
                    system_prompt = f"""你是{character_name}，一个语音对话助手。当前时间：{current_time}

你的性格特点：{character_personality}

回答要求：
1）保持你的角色设定，用符合你性格的语气和表达方式回答
2）使用日常口语，像朋友聊天一样自然
3）回答简短，控制在30字以内，说话时长不超过15秒
4）避免书面语、专业术语和长句子
5）直接回答重点，不要啰嗦
6）【重要】每次回答都要有不同的表达方式和内容，即使问题相同也要给出多样化的回答，可以从不同角度或用不同例子回答
7）【重要】不要使用任何括号（包括（）()【】[]）来添加动作、表情或语气描述，直接用文字表达即可"""
                    print(f"[get_ai_response] 使用角色提示词: 角色={character_name}, 性格={character_personality}, 时间={current_time}")
                else:
                    system_prompt = f"""你是一个语音对话助手。当前时间：{current_time}

回答要求：
1) 使用日常口语，像朋友聊天一样自然
2) 回答简短，控制在30字以内，说话时长不超过15秒
3) 避免书面语、专业术语和长句子
4) 直接回答重点，不要啰嗦
5) 【重要】每次回答都要有不同的表达方式，即使问题相同也要给出多样化的回答
6) 【重要】不要使用任何括号（包括（）()【】[]）来添加动作、表情或语气描述，直接用文字表达即可"""
                    print(f"[get_ai_response] 使用默认提示词, 时间={current_time}")
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content}
                    ],
                    stream=False,
                    temperature=1.0,  # 提高温度让回答更有创意和个性
                    max_tokens=100,  # 限制回答长度
                    top_p=0.95,  # 添加top_p采样增加随机性
                    frequency_penalty=0.5,  # 添加频率惩罚避免重复
                    presence_penalty=0.3  # 添加存在惩罚鼓励新内容
                )
                
                output = response.choices[0].message.content
                print(f"[get_ai_response] ✅ API调用成功")
                print(f"[get_ai_response] AI原始回答: {output}")
                
                # 清理括号内的描述性词语（避免TTS直接读出来）
                import re
                if output:
                    # 移除中文括号及其内容：（温柔轻笑）
                    output = re.sub(r'[（(].*?[）)]', '', output)
                    # 移除方括号及其内容：[笑声]
                    output = re.sub(r'[【\[].*?[】\]]', '', output)
                    # 移除可能的书名号等其他标记
                    output = re.sub(r'[《<].*?[》>]', '', output)
                    # 清理多余空格
                    output = re.sub(r'\s+', ' ', output).strip()
                    print(f"[get_ai_response] 清理后回答: {output}")
                
                # 保存输出文本
                with open(output_text, 'w', encoding='utf-8') as file:
                    file.write(output if output else "")
                
                print(f"[get_ai_response] 答复已保存到: {output_text}")
                return output if output else ""
                
            except Exception as e:
                error_msg = str(e)
                print(f"[get_ai_response] ❌ API调用失败 (尝试 {attempt + 1}/{retries}): {error_msg}")
                
                # 检查是否是网络超时
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    print("[get_ai_response] ⚠️ 网络超时，请检查网络连接")
                
                if attempt < retries - 1:
                    import time
                    print(f"[get_ai_response] 等待{delay}秒后重试...")
                    time.sleep(delay)
                else:
                    # 最后一次失败，返回默认回答
                    default_response = "抱歉，我现在无法回答，请稍后再试。"
                    print(f"[get_ai_response] 使用默认回答: {default_response}")
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
    【已废弃】请使用 backend.tts_service.TTSService 代替
    
    使用 GPT-SoVITS 进行文字转语音
    
    Args:
        text: 要合成的文字
        output_path: 输出音频路径
        ref_audio_path: 参考音频路径（用于音色克隆）
    
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    print("⚠️ 警告：text_to_speech() 函数已废弃，请使用 TTSService 类")
    print("⚠️ 该函数不会读取 audio_config.json 配置文件")
    
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