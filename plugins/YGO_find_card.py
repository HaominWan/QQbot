#方案一：爬虫从网页抓包
#方案二：调动网页机器人
#方案三：调用API

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

#方案一：

def get_card_info(card_name):
    services = ChromeService(executable_path="")
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=services, options=options)
    card_info = []

    try:
        driver.get("https://db.yugioh-card-cn.com/card_search.action.html")
        #不清楚这个'search_box'是不是这个id，这里只是一个例子
        search_box = driver.find_element(By.ID, "search_box")
        search_box.send_keys(card_name)
        search_box.send_keys(Keys.RETURN)
        WebDriverWait(driver, 10).until(
            #不清楚这个'card_info'是不是这个id，这里只是一个例子
            EC.presence_of_element_located((By.ID, "card_info"))
        )
        #以下为模拟运行，还没有区分卡片类型，甚至连这个element是否存在都没有判断
        cards = driver.find_elements(By.CLASS_NAME, "card_item")[:10]
        for card in cards:
            name = card.find_element(By.CLASS_NAME, "card_name").text
            effect = card.find_element(By.CLASS_NAME, "card_effect").text
            image_url = card.find_element(By.TAG_NAME, "img").get_attribute("src")
            card_type = card.find_element(By.CLASS_NAME, "card_type").text
            atk = card.find_element(By.CLASS_NAME, "card_atk").text
            defense = card.find_element(By.CLASS_NAME, "card_def").text
            attribute = card.find_element(By.CLASS_NAME, "card_attribute").text

            card_info.append({
                "name": name,
                "effect": effect,
                "image_url": image_url,
                "card_type": card_type,
                "atk": atk,
                "def": defense,
                "defense": defense,
                "attribute": attribute
            })

        return card_info
    finally:
        driver.quit()


#方案二：
