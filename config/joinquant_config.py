# -*- coding: utf-8 -*-
"""聚宽 JQData 配置 —— 全部从环境变量读取，不要在这里写死账号密码"""

import os

JOIQUANT_PHONE = os.environ.get("JOINQUANT_PHONE", "")
JOIQUANT_PASSWORD = os.environ.get("JOINQUANT_PASSWORD", "")


def assert_configured():
    if not JOIQUANT_PHONE or not JOIQUANT_PASSWORD:
        raise RuntimeError(
            "缺少聚宽账号配置。请设置环境变量 JOINQUANT_PHONE / JOINQUANT_PASSWORD"
        )
