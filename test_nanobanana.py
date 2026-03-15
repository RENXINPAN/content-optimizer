"""
test_nanobanana.py - 测试 Nano Banana 换文字效果

用法:
    export OPENROUTER_API_KEY="your-key"
    python test_nanobanana.py

会上传竖版样图，让 Nano Banana 保持风格只替换标题文字，输出新图片。
"""
import os
import sys
import json
import base64
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
if not OPENROUTER_API_KEY:
    print("请设置 OPENROUTER_API_KEY 环境变量")
    sys.exit(1)

# 样图路径（你需要把样图放到这个路径，或者改成你的路径）
SAMPLE_VERTICAL = "sample_vertical.png"    # 竖版样图
SAMPLE_HORIZONTAL = "sample_horizontal.png"  # 横版样图

# 要替换的新标题
NEW_TITLE = "穷人存钱越存越穷\n这不是鸡汤是数学"


def encode_image(path):
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode()


def generate_with_nanobanana(sample_path, new_text, output_path):
    """上传样图 + 让 Nano Banana 保持风格替换文字"""
    
    img_b64 = encode_image(sample_path)
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/RENXINPAN/content-optimizer",
        "X-Title": "Content Optimizer - Finance Images"
    }
    
    prompt = f"""Look at this image carefully. I want you to create a NEW image that:
1. Keeps the EXACT same visual style, layout, background color, font style, and decorative elements (the ant on the gold coin at the bottom)
2. Keeps the EXACT same color scheme (black text + orange highlighted text on beige/cream background)
3. ONLY replaces the text content with the following new Chinese text:

{new_text}

The first line should be in the same mixed black+orange style as the original.
Keep the same font size, weight, and positioning.
The image dimensions should match the original exactly.
Do NOT change anything else - same background, same ant+coin decoration, same overall composition."""

    payload = {
        "model": "google/gemini-3.1-flash-image-preview",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "modalities": ["image", "text"],
        "max_tokens": 4096,
    }
    
    print(f"正在调用 Nano Banana...")
    print(f"样图: {sample_path}")
    print(f"新标题: {new_text}")
    
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120
    )
    
    if resp.status_code != 200:
        print(f"❌ API 错误: {resp.status_code}")
        print(resp.text[:500])
        return None
    
    data = resp.json()
    message = data.get("choices", [{}])[0].get("message", {})
    
    # 尝试从 images 字段提取
    img_data = None
    images = message.get("images", [])
    if images:
        img_data = images[0].get("image_url", {}).get("url", "")
        print(f"从 message.images 提取到图片")
    
    # 尝试从 content 提取
    if not img_data:
        content = message.get("content", "")
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "image_url":
                        img_data = block.get("image_url", {}).get("url", "")
                        break
                    elif block.get("type") == "image":
                        img_data = block.get("url", "") or block.get("data", "")
                        break
            print(f"从 message.content 提取到图片")
        elif isinstance(content, str) and "base64" in content:
            img_data = content
            print(f"从 message.content(string) 提取到图片")
    
    if not img_data:
        print(f"❌ 未找到图片数据")
        print(f"Message keys: {list(message.keys())}")
        print(f"Content type: {type(message.get('content'))}")
        if isinstance(message.get('content'), str):
            print(f"Content preview: {message['content'][:200]}")
        return None
    
    # 解码保存
    if img_data.startswith("data:"):
        b64_str = img_data.split(",", 1)[1]
    else:
        b64_str = img_data
    
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(b64_str))
    
    print(f"✅ 图片已保存: {output_path}")
    return output_path


if __name__ == "__main__":
    os.makedirs("test_output", exist_ok=True)
    
    # 测试竖版
    if os.path.exists(SAMPLE_VERTICAL):
        generate_with_nanobanana(
            SAMPLE_VERTICAL,
            "穷人存钱越存越穷\n这不是鸡汤是数学",
            "test_output/vertical_new.png"
        )
    else:
        print(f"⚠️ 竖版样图不存在: {SAMPLE_VERTICAL}")
    
    print()
    
    # 测试横版
    if os.path.exists(SAMPLE_HORIZONTAL):
        generate_with_nanobanana(
            SAMPLE_HORIZONTAL,
            "穷人存钱越存越穷\n这不是鸡汤是数学",
            "test_output/horizontal_new.png"
        )
    else:
        print(f"⚠️ 横版样图不存在: {SAMPLE_HORIZONTAL}")
    
    print("\n完成！检查 test_output/ 目录查看结果")
