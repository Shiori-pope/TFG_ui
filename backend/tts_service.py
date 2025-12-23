import requests
import os
import shutil

class TTSService:
    """
    GPT-SoVITS TTS 服务封装
    提供简单的文字转语音功能
    """
    
    def __init__(self, api_url="http://127.0.0.1:9880"):
        self.api_url = api_url
        self.tts_endpoint = f"{api_url}/tts"
    
    def text_to_speech(self, text, output_path, ref_audio_path=None, prompt_text=None):
        """
        文字转语音
        
        Args:
            text: 要合成的文字
            output_path: 输出音频文件路径
            ref_audio_path: 参考音频路径（可选，用于音色克隆）
            prompt_text: 参考音频的文本（可选）
        
        Returns:
            bool: 成功返回 True，失败返回 False
        """
        try:
            # 如果没有提供参考音频，使用默认参考音频
            if not ref_audio_path:
                # 使用绝对路径（GPT-SoVITS API 需要绝对路径）
                base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
                ref_audio_path = os.path.join(base_dir, "static", "audios", "default_ref.wav")
                input_audio = os.path.join(base_dir, "static", "audios", "input.wav")
                
                # 如果默认参考不存在，创建一个（使用当前输入音频）
                if not os.path.exists(ref_audio_path):
                    if os.path.exists(input_audio):
                        os.makedirs(os.path.dirname(ref_audio_path), exist_ok=True)
                        shutil.copy(input_audio, ref_audio_path)
                        print(f"[TTS] 已创建默认参考音频: {ref_audio_path}")
                    else:
                        print(f"[TTS] 警告: 输入音频不存在，无法创建参考音频")
                        return False
                
                prompt_text = prompt_text or "你好"
            
            # 构建请求参数
            params = {
                "text": text,
                "text_lang": "zh",  # 中文
                "ref_audio_path": ref_audio_path,
                "prompt_text": prompt_text or "",
                "prompt_lang": "zh",
                "text_split_method": "cut5",
                "batch_size": 1,
                "media_type": "wav",
                "streaming_mode": False
            }
            
            # 发送 POST 请求
            print(f"[TTS] 正在合成语音: {text[:50]}...")
            response = requests.post(
                self.tts_endpoint,
                json=params,
                timeout=60
            )
            
            if response.status_code == 200:
                # 保存音频文件
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"[TTS] 语音合成成功: {output_path}")
                return True
            else:
                print(f"[TTS] 语音合成失败: {response.status_code}, {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            print("[TTS] 错误: 无法连接到 GPT-SoVITS 服务，请确保服务已启动")
            print(f"[TTS] 服务地址: {self.api_url}")
            return False
        except Exception as e:
            print(f"[TTS] 语音合成错误: {e}")
            return False
    
    def check_service(self):
        """
        检查 TTS 服务是否可用
        
        Returns:
            bool: 服务可用返回 True，否则返回 False
        """
        try:
            response = requests.get(f"{self.api_url}/", timeout=5)
            return True
        except:
            return False
