import requests
import os
import shutil
import json

class TTSService:
    """
    GPT-SoVITS TTS 服务封装
    提供简单的文字转语音功能
    """
    
    def __init__(self, api_url="http://127.0.0.1:9880"):
        self.api_url = api_url
        self.tts_endpoint = f"{api_url}/tts"
        
        # 加载配置文件路径
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
        self.characters_config_path = os.path.join(config_dir, "characters.json")
        self.tts_config_path = os.path.join(config_dir, "audio_config.json")
        
        # 加载配置
        self.characters_config = self._load_characters_config()
        self.tts_config = self._load_tts_config()
    
    def _load_characters_config(self):
        """加载角色配置文件（包含音频参考信息）"""
        try:
            if os.path.exists(self.characters_config_path):
                with open(self.characters_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"[TTS] ✅ 加载角色配置: {self.characters_config_path}")
                    return config
            else:
                print(f"[TTS] ⚠️ 角色配置文件不存在: {self.characters_config_path}")
                return {}
        except Exception as e:
            print(f"[TTS] ❌ 加载角色配置失败: {e}")
            return {}
    
    def _load_tts_config(self):
        """加载TTS技术配置文件"""
        try:
            if os.path.exists(self.tts_config_path):
                with open(self.tts_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    print(f"[TTS] ✅ 加载TTS配置: {self.tts_config_path}")
                    return config
            else:
                print(f"[TTS] ⚠️ TTS配置文件不存在，使用默认配置")
                return {'tts_settings': {'default_prompt_text': '你好'}}
        except Exception as e:
            print(f"[TTS] ❌ 加载TTS配置失败: {e}")
            return {'tts_settings': {'default_prompt_text': '你好'}}
    
    def _get_prompt_text(self, ref_audio_path):
        """根据参考音频路径获取对应的提示文本（从characters.json查找）"""
        if not self.characters_config or 'characters' not in self.characters_config:
            return self.tts_config.get('tts_settings', {}).get('default_prompt_text', '你好')
        
        # 提取文件名
        filename = os.path.basename(ref_audio_path)
        
        # 在角色配置中查找匹配的音频
        for character in self.characters_config.get('characters', []):
            char_audio = character.get('ref_audio', '')
            if char_audio and os.path.basename(char_audio) == filename:
                prompt = character.get('ref_audio_text', '你好')
                print(f"[TTS] 📝 找到角色 '{character.get('name')}' 的提示文本: {prompt}")
                return prompt
        
        # 使用默认值
        default_prompt = self.tts_config.get('tts_settings', {}).get('default_prompt_text', '你好')
        print(f"[TTS] 📝 使用默认提示文本: {default_prompt}")
        return default_prompt
    
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
            # 获取项目根目录
            base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
            
            # 如果没有提供参考音频，使用默认参考音频
            if not ref_audio_path:
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
            else:
                # 如果是相对路径，转换为绝对路径（GPT-SoVITS API 需要绝对路径）
                if not os.path.isabs(ref_audio_path):
                    ref_audio_path = os.path.abspath(os.path.join(base_dir, ref_audio_path))
                    print(f"[TTS] 📁 转换为绝对路径: {ref_audio_path}")
            
            # 检查参考音频文件是否存在
            if not os.path.exists(ref_audio_path):
                print(f"[TTS] ❌ 参考音频文件不存在: {ref_audio_path}")
                return False
            
            # 确保输出路径也是绝对路径
            if not os.path.isabs(output_path):
                output_path = os.path.abspath(os.path.join(base_dir, output_path))
                print(f"[TTS] 📁 输出路径: {output_path}")
            
            # 如果未指定prompt_text，从配置文件中获取
            if prompt_text is None:
                prompt_text = self._get_prompt_text(ref_audio_path)
            
            # 构建请求参数
            # GPT-SoVITS 支持的语言代码：
            # zh: 中文
            # en: 英文
            # ja: 日语
            # ko: 韩语
            # yue: 粤语
            # auto: 自动检测（推荐）
            params = {
                "text": text,
                "text_lang": "auto",  # 使用自动检测，支持多语种
                "ref_audio_path": ref_audio_path,
                "prompt_text": prompt_text,
                "prompt_lang": "auto",  # 参考音频语言也使用自动检测
                "text_split_method": "cut5",
                "batch_size": 1,
                "media_type": "wav",
                "streaming_mode": False
            }
            
            # 发送 POST 请求
            print(f"[TTS] 正在合成语音: {text[:50]}...")
            print(f"[TTS] 参考音频: {ref_audio_path}")
            print(f"[TTS] API地址: {self.tts_endpoint}")
            
            response = requests.post(
                self.tts_endpoint,
                json=params,
                timeout=60
            )
            
            print(f"[TTS] 响应状态码: {response.status_code}")
            print(f"[TTS] 响应Content-Type: {response.headers.get('Content-Type', 'unknown')}")
            
            if response.status_code == 200:
                # 检查响应类型
                content_type = response.headers.get('Content-Type', '')
                if 'audio' not in content_type and 'octet-stream' not in content_type:
                    print(f"[TTS] 警告: 响应类型异常: {content_type}")
                    print(f"[TTS] 响应内容前100字符: {response.text[:100]}")
                
                # 检查响应大小
                content_length = len(response.content)
                print(f"[TTS] 响应数据大小: {content_length} bytes")
                
                if content_length < 1000:
                    print(f"[TTS] 警告: 音频数据太小，可能生成失败")
                    print(f"[TTS] 响应内容: {response.text[:200]}")
                    return False
                
                # 保存音频文件
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"[TTS] ✅ 语音合成成功: {output_path}")
                return True
            else:
                print(f"[TTS] ❌ 语音合成失败: {response.status_code}")
                print(f"[TTS] 错误响应: {response.text[:500]}")
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
