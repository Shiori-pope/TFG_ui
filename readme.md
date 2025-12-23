# 数据处理&项目评测

基于 JoyGen 镜像的视频处理和合成评测工具集。

## 目录结构

- `/audio` - 音频文件挂载目录
- `/video` - 视频文件挂载目录
- `/results` - 原始结果挂载目录
- `/testdata` - 测试视频输入(mp4格式,需包含人脸)
- `/mid` - 视频切分后的中间文件存放目录
- `/out` - 合成后的视频输出目录
- `/analysis` - 最终评测输出文件目录
- `/pretrained_models` - 预训练模型存放目录

## 主要脚本

### video_cut_done.py
测试视频切分工具,生成中间文件:
- 输出: 50个 256×256 分辨率的视频片段
- 时长: 每个片段 10 秒

### cross_sample_synth_infer.py
交叉推理合成工具,用于生成测试视频

## 使用说明

1. 将测试视频放入 `/testdata` 目录
2. 将预训练模型放入 `/pretrained_models` 目录
3. 确保docker已启动，且安装了joygen:v1.0镜像 和 digital-human-eval:v4 镜像
4. 直接运行 `video_cut.py` 切分视频,这一步通常较快
5. 直接运行 `cross_sample_synth_infer.py` 进行合成推理，这一步大约需要数小时
6. 直接运行 `cacluate.py` 计算评测指标，结果会输出到 `/results` 目录，指标会打印到控制台，这一步大约需要20分钟