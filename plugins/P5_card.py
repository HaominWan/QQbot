import base64

from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

async def get_card(message):
    services = EdgeService(executable_path="")#Edgedriver路径
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 无头模式
    options.add_argument("--disable-gpu")  # 禁用 GPU 加速
    options.add_argument("--no-sandbox")  # 解决 DevToolsActivePort 文件不存在的报错
    options.add_argument("--disable-dev-shm-usage")  # 解决资源限制问题
    
    driver = webdriver.Edge(service=services, options=options)
    
    try:
        driver.get("https://yuluoxk.cn/p5/")
        
        # 定位 content 元素并输入数据
        text_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "content"))
        )
        text_box.send_keys(message)
        
        # 定位 canvas-text 元素并获取截图
        canvas_text = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "canvas-text"))
        )
        screenshot = canvas_text.screenshot_as_png
        image_base64 = base64.b64encode(screenshot).decode('utf-8')
        cq_code = f"[CQ:image,file = base64://{image_base64}, type = show, id = 40000]"
        return cq_code
        
    
    finally:
        driver.quit()