"""
游戏王查卡模块 —— 爬取 db.yugioh-card-cn.com，支持中文卡名搜索。
使用 Edge 无头浏览器；驱动版本通过 httpx+代理 自动下载并缓存。
"""

import asyncio
import io
import os
import subprocess
import zipfile
from pathlib import Path

import httpx
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import PROXY_URL

_SEARCH_URL = "https://db.yugioh-card-cn.com/card_search.action.html"

# We removed manual edgedriver downloads, now relying on selenium manager for Chrome.


# ── selenium helpers ───────────────────────────────────────────────────────────

def _make_driver() -> webdriver.Chrome:
    options = ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--ignore-certificate-errors")
    
    # We use Selenium Manager to automatically fetch the driver for Chrome without explicit proxy logic here.
    return webdriver.Chrome(service=ChromeService(), options=options)


# ── message segment helpers ────────────────────────────────────────────────────

def _text_seg(text: str) -> dict:
    return {"type": "text", "data": {"text": text}}


def _image_seg(url: str) -> dict:
    return {"type": "image", "data": {"file": url, "type": "show"}}


import urllib.parse
import json
import base64

# ── scraping logic ─────────────────────────────────────────────────────────────

def _scrape_cards(card_name: str) -> list:
    """Synchronous scrape — run inside asyncio.to_thread."""
    driver = _make_driver()
    try:
        params = {
            "titleId": "1",
            "keyword": card_name,
            "searchType": "1",
            "keywordLang": "0", "cardType": "", "starList": [], "penScaleList": [], "linkMarkerList": [],
            "linkCondition": "1", "atkFrom": "", "atkTo": "", "defFrom": "", "defTo": "", "attributeList": [],
            "effectList": [], "speciesList": [], "otherItemList": [], "otherCondition": "1", "exclusionList": [],
            "linkBtn": [], "sort": "1", "ullist": 0, "pageSize": "10", "page": "1", "mode": "1"
        }
        
        # User provided explicit encoding format where quotes remain unescaped:
        json_str = json.dumps(params, ensure_ascii=False, separators=(',', ':'))
        # Only encode { } [ ] safe allows quotes and colons commas
        encoded_params = urllib.parse.quote(json_str, safe='"/:,')
        direct_url = f"https://db.yugioh-card-cn.com/card_search.action_list.html?params={encoded_params}"
        
        driver.get(direct_url)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".t_row"))
            )
        except Exception:
            pass

        card_entries = []
        
        items = driver.find_elements(By.CSS_SELECTOR, ".t_row")
            
        for card in items[:5]:
            try:
                name = card.find_element(By.CSS_SELECTOR, ".card_name").text.strip()
                    
                try:
                    effect = card.find_element(By.CLASS_NAME, "box_card_text").text.strip()
                except:
                    effect = ""
                    
                types = []
                # Clean up duplicated elements by tracking seen
                seen_types = set()
                for e in card.find_elements(By.CSS_SELECTOR, ".box_card_spec span"):
                    t = e.text.strip().replace("\n", " ").replace("【", "").replace("】", "")
                    if t and t not in seen_types and "link" not in t.lower() and "SPELL" not in t:
                        seen_types.add(t)
                        types.append(t)
                
                image_url = ""
                try:
                    img = card.find_element(By.CSS_SELECTOR, ".box_card_img img")
                    image_url = img.get_attribute("src") or ""
                except Exception:
                    pass

                card_entries.append({
                    "name": name, "effect": effect,
                    "types": types, "image_url": image_url,
                })
            except Exception:
                continue

        if not card_entries:
            return [_text_seg(f"未找到「{card_name}」相关卡片。")]

        segments: list = []
        for i, entry in enumerate(card_entries):
            lines = [f"【{entry['name']}】 {' '.join(entry['types'])}"]
            eff = entry["effect"]
            lines.append(eff[:200] + ("…" if len(eff) > 200 else ""))

            if i > 0:
                segments.append(_text_seg("\n\n─────────────────\n\n"))
            segments.append(_text_seg("\n".join(lines)))
            if entry.get("image_url"):
                try:
                    # Download image directly to bypass NapCat timeout/blocking issues
                    with httpx.Client(verify=False, timeout=10.0, proxies=PROXY_URL) as client:
                        resp = client.get(entry["image_url"], headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
                        if resp.status_code == 200:
                            b64_data = base64.b64encode(resp.content).decode("utf-8")
                            segments.append(_image_seg(f"base64://{b64_data}"))
                        else:
                            segments.append(_image_seg(entry["image_url"]))
                except Exception as e:
                    print(f"Failed to download image {entry['image_url']}: {e}")
                    segments.append(_image_seg(entry["image_url"]))

        return segments
    finally:
        driver.quit()


# ── public API ─────────────────────────────────────────────────────────────────

async def get_card_info(card_name: str) -> list:
    """
    Search for up to 5 YGO cards matching card_name.
    Returns a flat OneBot message segment list (text + image per card).
    """
    try:
        return await asyncio.to_thread(_scrape_cards, card_name)
    except Exception as exc:
        print(f"[YGO] Scrape error: {exc}")
        return [_text_seg(f"[YGO] 查询失败：{exc}")]