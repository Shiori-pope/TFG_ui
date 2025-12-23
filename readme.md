# 数据处理&项目评测

基于 JoyGen 镜像的视频处理和合成评测工具集。

## 资源下载

### 测试视频数据集
- 下载链接: [Google Drive - 测试视频](https://drive.google.com/drive/folders/1FwQoBd1ZrBJMrJE3ZzlNhK8xAe1OYGjX)
- 放置位置: `/testdata` 目录

### 预训练模型
- 下载链接: [Google Drive - 预训练模型](https://drive.google.com/file/d/1kvGsljFRnXKUK_ETdd49jJy8DbdgZKkE/edit)
- 放置位置: `/pretrained_models` 目录

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

### video_cut.py
视频切分工具，基于 Docker 容器运行
- **功能**: 从 testdata 视频中随机切割片段
- **输出**: 50 个 256×256 分辨率的视频片段到 `/mid` 目录
- **时长**: 每个片段 10 秒
- **用法**: `python video_cut.py` (支持 `-i`, `-o`, `-img` 参数自定义)
- **依赖**: 需要 `joygen:v1.0` Docker 镜像

### cross_sample_synth_infer.py
交叉采样合成推理工具
- **功能**: 使用 JoyGen 模型进行视频-音频交叉合成
- **输入**: `/mid` 目录的视频片段
- **输出**: 合成视频到 `/out` 目录
- **用法**: `python cross_sample_synth_infer.py`
- **依赖**: 需要 `joygen:v1.0` Docker 镜像和预训练模型
- **耗时**: 数小时（取决于片段数量和硬件）

### cacluate.py
视频质量评估工具
- **功能**: 计算 LSE (唇形同步误差) 和 FID (图像质量) 指标
- **输入**: `/mid` (原始视频) 和 `/out` (生成视频)
- **输出**: 评估结果到 `/analysis` 目录，指标打印到控制台
- **用法**: `python cacluate.py`
- **依赖**: 需要 `digital-human-eval:v4` Docker 镜像
- **耗时**: 约 20 分钟

## 使用说明

### 准备工作
1. 下载测试视频并放入 `/testdata` 目录（见上方下载链接）
2. 下载预训练模型并解压到 `/pretrained_models` 目录（见上方下载链接）
3. 确保 Docker 已启动，且安装了 `joygen:v1.0` 镜像和 `digital-human-eval:v4` 镜像

### 执行流程
4. 直接运行 `video_cut.py` 切分视频,这一步通常较快
5. 直接运行 `cross_sample_synth_infer.py` 进行合成推理，这一步大约需要数小时
6. 直接运行 `cacluate.py` 计算评测指标，结果会输出到 `/results` 目录，指标会打印到控制台，这一步大约需要20分钟