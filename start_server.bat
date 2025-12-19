@echo off
chcp 65001 >nul
echo ========================================
echo   华丽对话系统 - 快速启动
echo ========================================
echo.

echo [1/3] 检查环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python未安装或不在PATH中
    pause
    exit /b 1
)
echo ✓ Python环境正常

echo.
echo [2/3] 检查静态资源...
if not exist "static\images\bg_anime1.jpg" (
    echo ⚠ 背景图片不存在，正在生成...
    python generate_backgrounds.py
)
echo ✓ 静态资源就绪

echo.
echo [3/3] 启动Flask服务器...
echo ✓ 服务器即将启动
echo.
echo ========================================
echo   访问地址: http://localhost:5001/chat_system
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.

python app.py
