"""
Tushare配置模块
用于管理Tushare Pro API配置
"""

import os

# Tushare Pro Token
# 从环境变量或配置文件读取Token
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', '')

def get_tushare_pro():
    """获取Tushare Pro接口实例"""
    import tushare as ts
    ts.set_token(TUSHARE_TOKEN)
    return ts.pro_api()

# 如果需要从文件读取Token，可以使用以下方式
def load_token_from_file(filepath='data/.tushare_token'):
    """从文件加载Token"""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return f.read().strip()
    return None
