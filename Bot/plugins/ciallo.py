CIALLO_GREETING = "Ciallo～(∠・ω< )⌒☆ \u200b"

CIALLO_MESSAGE = f"""【主服】{CIALLO_GREETING}
平面 https://map.npucraft.com
三维 https://map.npucraft.com/bluemap
【工业服】{CIALLO_GREETING}
平面 https://map.npucraft.com/dynmap-industry
三维 https://map.npucraft.com/bluemap-industry
【资源服】{CIALLO_GREETING}
平面 https://map.npucraft.com/dynmap-resource
【狐务器】{CIALLO_GREETING}
数据面板 https://plan.npucraft.com/
全部地图请发送关键词“{CIALLO_GREETING}”"""


def get_message() -> str:
    return CIALLO_MESSAGE
