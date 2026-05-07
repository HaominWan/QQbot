# 导出角色对外接口，供 persona_engine 调用。
#
# 快速接入自定义角色：
#   1. 复制 example_card.py，实现 get_xxx_role(user_qq, bot_qq) 函数。
#   2. 在下方 import 并导出它。
#   3. 在 persona_engine.py 的 get_system_role() 中引用即可。
#
# 示例（取消注释后使用）：
# from .example_card import get_example_intimate_role, get_example_casual_role

try:
    from .Murasame_goshujin import *
    from .Murasame_customers import *
except ImportError:
    # 自定义角色文件不在仓库中时忽略，使用者自行实现并导入。
    pass