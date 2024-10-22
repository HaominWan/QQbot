import bot
from selenium import webdriver
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

async def handle_card_info(card_info):
    CQ_code = card_info["name"]
    image_url = card_info["image_url"]
    CQ_code += f"[CQ:image,file={image_url},type=show,id = 40000]" 
    for info in card_info["card_type"]:
        CQ_code += f"{info} "
    CQ_code += "\n"
    if card_info["card_type"][0] == "怪兽":
        if card_info["card_type"][2] == "连接":
            CQ_code += f"LINK: {card_info['LINK']} ATK: {card_info['atk']} {card_info['race']}/{card_info['element']}\n"
        elif card_info["card_type"][2] == "XYZ":
            CQ_code += f"CLASS: {card_info['CLASS']} ATK: {card_info['atk']} DEF: {card_info['def']} {card_info['race']}/{card_info['element']}\n"
        else:
            CQ_code += f"STAR: {card_info['STAR']} ATK: {card_info['atk']} DEF: {card_info['def']} {card_info['race']}/{card_info['element']}\n"
    CQ_code += f"效果: {card_info['effect']}"
    return await bot.bot_interfaces["decode_CQ_to_message"](CQ_code)

async def get_card_info(card_name):
    services = EdgeService(executable_path="")#Edgedriver路径
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # 无头模式
    options.add_argument("--disable-gpu")  # 禁用 GPU 加速
    options.add_argument("--no-sandbox")  # 解决 DevToolsActivePort 文件不存在的报错
    options.add_argument("--disable-dev-shm-usage")  # 解决资源限制问题

    driver = webdriver.Edge(service=services, options=options)
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
            card_info = {}
            name = card.find_element(By.TAG_NAME, "h3").text.strip()
            effect = card.find_element(By.CLASS_NAME, "effect").text.strip()
            card_type_elements = card.find_elements(By.CSS_SELECTOR, ".type a")
            card_type = [element.text.strip() for element in card_type_elements]
            detail_url = card.find_element(By.TAG_NAME, "a").get_attribute("href")

            # 访问详情页以获取图片 URL
            driver.get(detail_url)
            image_url = driver.find_element(By.CLASS_NAME, "card-img").get_attribute("src")
            driver.back()

            card_info["name"] = name
            card_info["effect"] = effect
            card_info["image_url"] = image_url
            card_info["card_type"] = card_type
            
            if card_type[0] is '怪兽':
                if card_type[2] is '连接':
                    meta_info = driver.find_element(By.CLASS_NAME, "meta").text.strip()
                    meta_parts = meta_info.split(" / ")
                    card_info["LINK"] = str(meta_parts[0])
                    card_info["atk"] = str(meta_parts[1])
                    card_info["race"] = str(meta_parts[2])
                    card_info["element"] = str(meta_parts[3])
                if card_type[2] is 'XYZ':
                    meta_info = driver.find_element(By.CLASS_NAME, "meta").text.strip()
                    meta_parts = meta_info.split(" / ")
                    card_info["CLASS"] = str(meta_parts[0])
                    card_info["atk"] = str(meta_parts[1])
                    card_info["def"] = str(meta_parts[2])
                    card_info["race"] = str(meta_parts[3])
                    card_info["element"] = str(meta_parts[4])
                else:
                    meta_info = driver.find_element(By.CLASS_NAME, "meta").text.strip()
                    meta_parts = meta_info.split(" / ")
                    card_info["STAR"] = str(meta_parts[0])
                    card_info["atk"] = str(meta_parts[1])
                    card_info["def"] = str(meta_parts[2])
                    card_info["race"] = str(meta_parts[3])
                    card_info["element"] = str(meta_parts[4])
            message_box.append(await handle_card_info(card_info))
        return message_box
    finally:
        driver.quit()
