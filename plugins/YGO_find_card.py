from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

async def handle_card_info(card_info):
    
    pass
async def get_card_info(card_name):
    services = ChromeService(executable_path="")
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=services, options=options)
    message_box = []
    try:
        driver.get("https://db.yugioh-card-cn.com/card_search.action.html")
        search_box = driver.find_element(By.ID, "search_bar")
        search_box.send_keys(card_name)
        search_box.send_keys(Keys.RETURN)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "card-item"))
        )
        cards = driver.find_elements(By.CLASS_NAME, "card-item")[:10]
        for card in cards:
            card_info = []
            name = card.find_element(By.TAG_NAME, "h3").text.strip()
            effect = card.find_element(By.CLASS_NAME, "effect").text.strip()
            card_type_elements = card.find_elements(By.CSS_SELECTOR, ".type a")
            card_type = [element.text.strip() for element in card_type_elements]
            detail_url = card.find_element(By.TAG_NAME, "a").get_attribute("href")

            # 访问详情页以获取图片 URL
            driver.get(detail_url)
            image_url = driver.find_element(By.CLASS_NAME, "card-img").get_attribute("src")
            driver.back()

            card_info.append({
                "name": name,
                "effect": effect,
                "image_url": image_url,
                "card_type": card_type
            })
            
            if card_type[0] is '怪兽':
                if card_type[2] is '连接':
                    meta_info = driver.find_element(By.CLASS_NAME, "meta").text.strip()
                    meta_parts = meta_info.split(" / ")
                    card_info.append({
                        "LINK": str(meta_parts[0]),
                        "atk": str(meta_parts[1]),
                        "race": str(meta_parts[2]),
                        "element": str(meta_parts[3])
                    })
                if card_type[2] is 'XYZ':
                    meta_info = driver.find_element(By.CLASS_NAME, "meta").text.strip()
                    meta_parts = meta_info.split(" / ")
                    card_info.append({
                        "CLASS": str(meta_parts[0]),
                        "atk": str(meta_parts[1]),
                        "def": str(meta_parts[2]),
                        "race": str(meta_parts[3]),
                        "element": str(meta_parts[4])
                    })
                else:
                    meta_info = driver.find_element(By.CLASS_NAME, "meta").text.strip()
                    meta_parts = meta_info.split(" / ")
                    card_info.append({
                        "STAR": str(meta_parts[0]),
                        "atk": str(meta_parts[1]),
                        "def": str(meta_parts[2]),
                        "race": str(meta_parts[3]),
                        "element": str(meta_parts[4])
                    })
            message_box.append(await handle_card_info(card_info))
        return message_box
    finally:
        driver.quit()


#方案二：
