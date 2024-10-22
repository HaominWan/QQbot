import base64
import time
import os

from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

async def get_card(message):
    services = EdgeService(executable_path="D:/edgedriver_win64/msedgedriver.exe")#Edgedriver路径 130.0.2849.46 (正式版本) (64 位)
    
    options = webdriver.EdgeOptions()
    # options.use_chromium = True # 使用 Chromium 版本的 Edge
    options.add_argument("--ignore-certificate-errors") # 忽略 SSL 错误
    options.add_argument("--ignore-ssl-errors") # 忽略 SSL 错误
    options.add_argument("--ignore-certificate-errors-spki-list") # 忽略证书错误
    options.add_argument("--headless")  # 无头模式
    options.add_argument("--disable-gpu")  # 禁用 GPU 加速
    options.add_argument("--no-sandbox")  # 解决 DevToolsActivePort 文件不存在的报错
    options.add_argument("--disable-dev-shm-usage")  # 解决资源限制问题
    options.add_argument("--disable-extensions")  # 禁用扩展
    options.add_argument("--disable-infobars") # 禁用信息栏
    
    driver = webdriver.Edge(service=services, options=options)
    
    try:
        driver.get("https://yuluoxk.cn/p5/")
        
        # 定位 content 元素并输入数据
        text_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "content"))
        )
        text_box.send_keys(message)

        #确认消息写入完成
        WebDriverWait(driver, 10).until(
            EC.text_to_be_present_in_element_value((By.NAME, "content"), message)
        )
        #等一下活爹
        time.sleep(1)
        
        # 定位 canvas-text 元素并获取截图
        canvas_text = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#canvas-text"))
        )
        screenshot = canvas_text.screenshot_as_png

        if not os.path.exists('D:/QQbot/Bot/tmp'):
                os.makedirs('D:/QQbot/Bot/tmp/')
        temp_png = "D:/QQbot/Bot/tmp/" + str(time.time()) + '.png'
        with open(temp_png, 'wb') as f:
            f.write(screenshot)
        
        # 将图片编码为 base64
        with open(temp_png, 'rb') as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            
        cq_code = f"[CQ:image,file=base64://{image_base64},type=show,id=40000]"
        os.remove(temp_png)
        return cq_code
        
    finally:
        driver.quit()