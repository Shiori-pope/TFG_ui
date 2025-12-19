"""
生成背景图片占位符
为4个主题生成渐变背景图片
"""
from PIL import Image, ImageDraw
import os

def create_gradient_image(width, height, color1, color2, filename):
    """创建渐变背景图片"""
    image = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(image)
    
    # 解析颜色
    r1, g1, b1 = tuple(int(color1[i:i+2], 16) for i in (1, 3, 5))
    r2, g2, b2 = tuple(int(color2[i:i+2], 16) for i in (1, 3, 5))
    
    # 创建渐变
    for y in range(height):
        ratio = y / height
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.rectangle([(0, y), (width, y+1)], fill=(r, g, b))
    
    # 保存
    image.save(filename, 'JPEG', quality=95)
    print(f"✓ 已生成: {filename}")

def main():
    # 创建images目录
    os.makedirs('static/images', exist_ok=True)
    
    # 图片尺寸
    width, height = 1920, 1080
    
    # 生成4张主题背景
    themes = [
        ('bg_anime1.jpg', '#ff6b9d', '#ffc2d4'),  # 甜美 - 粉色系
        ('bg_anime2.jpg', '#00f0ff', '#bd00ff'),  # 赛博 - 蓝紫系
        ('bg_anime3.jpg', '#7b68ee', '#9370db'),  # 深夜 - 紫色系
        ('bg_anime4.jpg', '#ff69b4', '#ffa500'),  # 二次元 - 粉橙系
    ]
    
    for filename, color1, color2 in themes:
        filepath = os.path.join('static', 'images', filename)
        create_gradient_image(width, height, color1, color2, filepath)
    
    print("\n所有背景图片已生成完成！")
    print("位置: static/images/")
    print("\n提示: 这些是临时占位图片，建议替换为真实的二次元背景图")

if __name__ == '__main__':
    main()
