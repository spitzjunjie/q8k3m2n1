# -*- coding: utf-8 -*-
"""Rebuild akshare_helper.py with all accumulated fixes."""
import sys

PATH = "data/akshare_helper.py"

with open(PATH, "r", encoding="utf-8") as f:
    content = f.read()

# ============================================================
# Step 1: Add instance variables in __init__
# ============================================================
old_init = "        self._max_retries = 5  # 最大重试次数"
new_init = """        self._max_retries = 5  # 最大重试次数
        self._spot_em_snapshot = None  # 全市场实时行情快照缓存，避免按股票查询时重复全量拉取
        self._spot_sina_snapshot = None  # 新浪全市场快照缓存
        self._stock_news_cache = None  # 新闻数据实例级缓存，避免同一 helper 内重复拉取
        self._consecutive_network_failures = 0  # 连续网络失败计数，用于快速熔断"""

content = content.replace(old_init, new_init, 1)
print("Step 1 (init vars): OK")

# ============================================================
# Step 2: Replace _retry_request with fast-fail version
# ============================================================
old_retry_start = content.find("    def _retry_request(self, func, *args, **kwargs):")
old_retry_end = content.find("\n    def wrap_akshare", old_retry_start)

new_retry = """    def _retry_request(self, func, *args, **kwargs):
        \"\"\"带重试的请求，自动处理网络错误。连续网络失败 >= 3 次后进入快速熔断模式。\"\"\"
        FAST_FAIL_THRESHOLD = 3

        max_retries = 1 if self._consecutive_network_failures >= FAST_FAIL_THRESHOLD else self._max_retries
        last_error = None

        for attempt in range(max_retries):
            try:
                self._rate_limit()
                result = func(*args, **kwargs)
                self._consecutive_network_failures = 0
                return result
            except Exception as e:
                last_error = e
                error_str = str(e)

                is_network_error = any(x in error_str for x in [
                    'RemoteDisconnected', 'Connection aborted', 'ConnectionReset',
                    'ConnectionRefused', 'timed out', 'ReadTimeout',
                    'SSLError', 'EOF', 'getaddrinfo'
                ])

                if is_network_error:
                    self._consecutive_network_failures += 1
                    if attempt < max_retries - 1:
                        wait_time = self._base_wait_time * (attempt + 1) + random.uniform(0, 2)
                        print(f\"  网络错误，{wait_time:.1f}秒后重试 ({attempt + 1}/{max_retries}): {e}\")
                        time.sleep(wait_time)
                else:
                    self._consecutive_network_failures = 0
                    break

        raise last_error
"""

content = content[:old_retry_start] + new_retry + content[old_retry_end:]
print("Step 2 (_retry_request): OK")

# ============================================================
# Step 3: Add _get_spot_em_snapshot and _get_spot_sina_snapshot
# after wrap_akshare
# ============================================================
wrap_end = content.find("\n    def _rate_limit(self):", old_retry_start + len(new_retry))
# Actually find where wrap_akshare ends
wrap_start = content.find("    def wrap_akshare(self, func, *args, **kwargs):")
wrap_body_end = content.find("\n    def ", wrap_start + 1)
# The next method after wrap_akshare
next_method = content.find("\n    def ", wrap_body_end)

snapshot_methods = """
    def _get_spot_em_snapshot(self):
        \"\"\"全市场实时行情快照（东财），同一实例/同一天内只抓一次。

        按股票查询估值等方法应该复用这份快照做本地过滤，而不是
        每查一只股票就重新拉一次全市场行情——后者在东财接口不稳定时，
        会让每只股票都单独触发一轮 报错-重试-退避，把一次选股拖到几分钟。
        \"\"\"
        if self._spot_em_snapshot is not None:
            return self._spot_em_snapshot

        cache_key = "spot_em_snapshot"
        cached = self._get_cache(cache_key, days=1)
        if cached is not None:
            self._spot_em_snapshot = pd.DataFrame(cached)
            return self._spot_em_snapshot

        max_retries = 3
        for attempt in range(max_retries):
            try:
                df = ak.stock_zh_a_spot_em()
                if df is not None and not df.empty:
                    self._set_cache(cache_key, df.to_dict('records'))
                    self._spot_em_snapshot = df
                    return df
                break
            except Exception as e:
                error_str = str(e)
                is_connection_error = any(x in error_str for x in [
                    'RemoteDisconnected', 'Connection aborted', 'ConnectionReset',
                    'ConnectionRefused', 'timed out', 'ReadTimeout'
                ])
                if is_connection_error and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f\"东财实时行情连接失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries})\")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f\"东财实时行情获取失败: {e}\")
                    break
        return pd.DataFrame()

    def _get_spot_sina_snapshot(self):
        \"\"\"新浪全市场实时行情快照，同一实例/同一天内只抓一次。\"\"\"
        if self._spot_sina_snapshot is not None:
            return self._spot_sina_snapshot

        cache_key = "spot_sina_snapshot"
        cached = self._get_cache(cache_key, days=1)
        if cached is not None:
            self._spot_sina_snapshot = pd.DataFrame(cached)
            return self._spot_sina_snapshot

        try:
            spot_df = ak.stock_zh_a_spot()
            if spot_df is not None and not spot_df.empty:
                self._set_cache(cache_key, spot_df.to_dict('records'))
                self._spot_sina_snapshot = spot_df
                return spot_df
        except Exception as e:
            print(f\"新浪实时行情获取失败: {e}\")
        self._spot_sina_snapshot = pd.DataFrame()
        return self._spot_sina_snapshot

"""

content = content[:next_method] + snapshot_methods + content[next_method:]
print("Step 3 (snapshot methods): OK")

with open(PATH, "w", encoding="utf-8") as f:
    f.write(content)

try:
    compile(content, PATH, "exec")
    print("Syntax: OK after Step 3")
except SyntaxError as e:
    print(f"SyntaxError after Step 3: {e}")
    sys.exit(1)
