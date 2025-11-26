import jmcomic
import os
import glob
import re
import requests
from PIL import Image
from jmcomic.jm_exception import *

# 自定义HTML解析函数
def extract_basic_info_from_html(html_content, album_id):
    """从HTML内容中提取基本信息"""
    info = {
        'name': f'Album_{album_id}',
        'description': 'Custom download',
        'author': 'Unknown',
        'tags': [],
        'image_urls': []
    }
    
    # 尝试提取标题 - 多种可能的模式
    title_patterns = [
        r'<h1[^>]*class="[^"]*book-name[^"]*"[^>]*>([^<]+)</h1>',
        r'<h1[^>]*id="[^"]*book-name[^"]*"[^>]*>([^<]+)</h1>',
        r'<title>([^<]+)</title>',
        r'<h1[^>]*>([^<]+)</h1>',
        r'"name":\s*"([^"]+)"',
        r'name:\s*"([^"]+)"'
    ]
    
    for pattern in title_patterns:
        match = re.search(pattern, html_content, re.IGNORECASE | re.MULTILINE)
        if match:
            title = match.group(1).strip()
            if title and len(title) > 3 and '禁漫' not in title and 'JMComic' not in title:
                info['name'] = title
                break
    
    # 尝试提取图片URL - 寻找常见的图片URL模式
    img_patterns = [
        r'data-original="([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
        r'src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
        r'"url":\s*"([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
        r"'url':\s*'([^']+\.(?:jpg|jpeg|png|gif|webp))'",
    ]
    
    for pattern in img_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        if matches:
            info['image_urls'].extend(matches)
    
    return info

async def get_pdf(code):
    try: 
        temp_dir = f"Bot/tmp/{code}"
        pdf_name = f"Bot/tmp/{code}/{code}.pdf"
        
        # 确保临时目录存在
        os.makedirs(temp_dir, exist_ok=True)
        
        print(f"[INFO] 正在尝试访问内容 {code}...")
        print(f"[INFO] 使用改进的HTML解析策略...")
        
        # 策略1: 尝试不同的代码格式
        possible_codes = [code, str(code).zfill(6), f"JM{code}"]
        
        success = False
        album_info = None
        
        for attempt_code in possible_codes:
            print(f"[INFO] 尝试代码格式: {attempt_code}")
            
            try:
                # 使用requests直接获取HTML内容，然后手动解析
                domains = ['18comic.org', '18comic.vip', 'jm-comic2.cc']
                
                for domain in domains:
                    url = f"https://{domain}/album/{attempt_code}"
                    print(f"[INFO] 尝试访问: {url}")
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Referer': f'https://{domain}/',
                        'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                        'Sec-Ch-Ua-Mobile': '?0',
                        'Sec-Ch-Ua-Platform': '"Windows"',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'same-origin',
                        'Upgrade-Insecure-Requests': '1',
                        'Cache-Control': 'max-age=0',
                        'Connection': 'keep-alive'
                    }
                    
                    session = requests.Session()
                    session.verify = False
                    session.proxies = None  # 明确禁用代理
                    
                    try:
                        # 首先访问主页获取可能的cookies，并模拟真实的浏览行为
                        print(f"[INFO] 模拟浏览器访问主页...")
                        main_response = session.get(f"https://{domain}/", headers=headers, timeout=30)
                        
                        # 检查是否遇到Cloudflare保护
                        if "Just a moment" in main_response.text or "challenge" in main_response.text.lower():
                            print(f"[INFO] 检测到Cloudflare保护，等待10秒...")
                            import time
                            time.sleep(10)
                            
                            # 尝试再次访问主页
                            main_response = session.get(f"https://{domain}/", headers=headers, timeout=30)
                        
                        # 模拟浏览器行为：等待更长时间，然后访问目标页面
                        print(f"[INFO] 等待页面加载完成...")
                        import time
                        time.sleep(5)
                        
                        # 然后访问目标页面
                        response = session.get(url, headers=headers, timeout=30, allow_redirects=True)
                        
                        print(f"[INFO] 获取到页面，状态码: {response.status_code}")
                        
                        # 如果仍然遇到Cloudflare，再等待一段时间重试
                        retry_count = 0
                        while ("Just a moment" in response.text or "challenge" in response.text.lower()) and retry_count < 3:
                            retry_count += 1
                            print(f"[INFO] 仍然遇到Cloudflare保护，等待15秒后重试 (尝试 {retry_count}/3)...")
                            time.sleep(15)
                            response = session.get(url, headers=headers, timeout=30, allow_redirects=True)
                        
                        # 如果遇到重定向页面，尝试跟随重定向
                        if response.status_code == 200:
                            html_content = response.text
                            print(f"[INFO] 成功获取HTML内容，长度: {len(html_content)}")
                            
                            # 检查是否是重定向页面
                            if ("Redirecting" in html_content or len(html_content) < 10000) and "Just a moment" not in html_content:
                                # 尝试寻找JavaScript重定向
                                redirect_patterns = [
                                    r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',
                                    r'location\.href\s*=\s*["\']([^"\']+)["\']',
                                    r'window\.location\s*=\s*["\']([^"\']+)["\']',
                                    r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\'][^;]*;\s*url=([^"\']+)["\']'
                                ]
                                
                                for pattern in redirect_patterns:
                                    match = re.search(pattern, html_content, re.IGNORECASE)
                                    if match:
                                        redirect_url = match.group(1)
                                        if not redirect_url.startswith('http'):
                                            redirect_url = f"https://{domain}{redirect_url}"
                                        print(f"[INFO] 发现重定向URL: {redirect_url}")
                                        
                                        time.sleep(3)  # 等待更长时间
                                        response = session.get(redirect_url, headers=headers, timeout=30)
                                        if response.status_code == 200:
                                            html_content = response.text
                                            print(f"[INFO] 重定向后获取HTML内容，长度: {len(html_content)}")
                                        break
                            
                            # 使用自定义解析器
                            album_info = extract_basic_info_from_html(html_content, attempt_code)
                            print(f"[INFO] 解析到标题: {album_info['name']}")
                            print(f"[INFO] 发现图片: {len(album_info['image_urls'])} 个")
                            
                            # 如果仍然没有找到图片，尝试分析页面结构
                            if not album_info['image_urls'] and len(html_content) > 50000:
                                print(f"[INFO] 尝试更深入的图片提取...")
                                # 扩展图片搜索模式
                                extended_patterns = [
                                    r'data-src="([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
                                    r'data-lazy="([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
                                    r'"image":\s*"([^"]+\.(?:jpg|jpeg|png|gif|webp))"',
                                    r'src="([^"]*cdn[^"]*\.(?:jpg|jpeg|png|gif|webp))"',
                                    r'url\(["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp))["\']',
                                ]
                                
                                for pattern in extended_patterns:
                                    matches = re.findall(pattern, html_content, re.IGNORECASE)
                                    if matches:
                                        album_info['image_urls'].extend(matches)
                                        print(f"[INFO] 通过扩展模式找到 {len(matches)} 个图片URL")
                                
                                # 去重
                                album_info['image_urls'] = list(set(album_info['image_urls']))
                                print(f"[INFO] 去重后共有 {len(album_info['image_urls'])} 个图片URL")
                            
                            if album_info['image_urls']:
                                success = True
                                break
                                
                    except Exception as e:
                        print(f"[WARN] 域名 {domain} 失败: {str(e)[:50]}...")
                        continue
                
                if success:
                    break
                    
            except Exception as e:
                print(f"[WARN] 代码 {attempt_code} 失败: {str(e)[:100]}...")
                continue
        
        if not success or not album_info or not album_info['image_urls']:
            print(f"[ERROR] 无法获取图片信息")
            print(f"[INFO] 建议:")
            print(f"[INFO] 1. 检查内容代码是否正确")
            print(f"[INFO] 2. 网站可能需要登录cookies")
            print(f"[INFO] 3. 网站结构可能已经改变")
            return 0
        
        # 下载图片
        print(f"[INFO] 开始下载 {len(album_info['image_urls'])} 张图片...")
        image_files = []
        
        for i, img_url in enumerate(album_info['image_urls'][:50]):  # 限制最多50张
            try:
                if not img_url.startswith('http'):
                    continue
                    
                print(f"[INFO] 下载图片 {i+1}/{len(album_info['image_urls'])}: {img_url[:50]}...")
                
                response = requests.get(img_url, headers=headers, timeout=30, verify=False)
                if response.status_code == 200:
                    # 确定文件扩展名
                    content_type = response.headers.get('content-type', '')
                    if 'jpeg' in content_type or 'jpg' in content_type:
                        ext = '.jpg'
                    elif 'png' in content_type:
                        ext = '.png'
                    elif 'webp' in content_type:
                        ext = '.webp'
                    else:
                        ext = '.jpg'  # 默认
                    
                    file_path = os.path.join(temp_dir, f"{i+1:03d}{ext}")
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    image_files.append(file_path)
                    print(f"[SUCCESS] 图片 {i+1} 下载完成")
                else:
                    print(f"[WARN] 图片 {i+1} 下载失败: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"[WARN] 跳过图片 {i+1}: {str(e)[:50]}...")
                continue
        
        if not image_files:
            print(f"[ERROR] 没有成功下载任何图片")
            return 0
        
        print(f"[INFO] 成功下载 {len(image_files)} 张图片")
        
        # 生成PDF
        print(f"[INFO] 正在生成PDF...")
        
        images = []
        for img_path in image_files:
            try:
                img = Image.open(img_path)
                if img.mode == 'RGBA':
                    img = img.convert('RGB')
                images.append(img)
            except Exception as e:
                print(f"[WARN] 跳过文件 {img_path}: {e}")
        
        if not images:
            print(f"[ERROR] 没有有效的图片")
            return 0
        
        # 保存PDF
        images[0].save(pdf_name, save_all=True, append_images=images[1:])
        
        # 清理
        for img in images:
            img.close()
        
        for file in image_files:
            try:
                os.remove(file)
            except:
                pass
        
        print(f"[SUCCESS] PDF生成完成: {pdf_name}")
        return pdf_name
        print(f"[SUCCESS] PDF生成完成: {pdf_name}")
        return pdf_name
        
    except MissingAlbumPhotoException as e:
        print(f"[ERROR] Missing album photo: {e}")
        return 0
    except Exception as e:
        print(f"[ERROR] Unexpected error occurred: {e}")
        # 如果是403错误（被识别为爬虫或地区限制）
        if "403" in str(e) or "ip地区禁止访问" in str(e) or "爬虫被识别" in str(e):
            print(f"[ERROR] Access denied (403) - possible causes:")
            print(f"[ERROR] 1. IP region restriction")
            print(f"[ERROR] 2. Bot detection")
            print(f"[ERROR] 3. Need valid cookies/login")
            print(f"[ERROR] 4. Need proxy")
        
        # 打印完整的错误信息用于调试
        import traceback
        traceback.print_exc()
        return 0

# if __name__ == "__main__":
#     import asyncio
#     async def main():
#         pdf_name = await get_pdf("432590")
#         print(pdf_name)
#     asyncio.run(main())