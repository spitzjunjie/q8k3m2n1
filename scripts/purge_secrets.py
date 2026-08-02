#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
密钥清理脚本 —— 把仓库里所有硬编码的凭证改成环境变量读取
====================================================================
在 multi_strategy_trading（公开仓库）根目录运行：

    python scripts/purge_secrets.py --dry-run    # 先看会改什么
    python scripts/purge_secrets.py              # 实际修改

在 stock_intelligence（父仓库）根目录也跑一遍，它会自动识别。

脚本是幂等的：改过之后再跑不会重复改。
改完会自动扫描一遍，确认没有残留。
====================================================================
"""

import argparse
import os
import re
import sys

# --------------------------------------------------------------
# 1. 精确替换规则： (文件, 旧模式正则, 新内容)
#    用正则匹配"变量名 = 字符串字面量"，不写死密钥本身，
#    这样脚本本身不含任何密钥，可以安全提交。
# --------------------------------------------------------------

RULES = [
    # ---------- multi_strategy_trading（公开仓库）----------
    (
        "config/tushare_config.py",
        r"TUSHARE_TOKEN\s*=\s*os\.environ\.get\(\s*['\"]TUSHARE_TOKEN['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)",
        "TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', '')",
    ),
    (
        "strategy_discovery/financial_nlp.py",
        r"HF_TOKEN\s*=\s*['\"][^'\"]{12,}['\"]",
        "HF_TOKEN = os.environ.get('HF_TOKEN', '')",
    ),
    (
        "strategy_discovery/financial_nlp.py",
        r"GROQ_API_KEY\s*=\s*['\"][^'\"]{12,}['\"]",
        "GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')",
    ),
    (
        "strategy_discovery/groq_client.py",
        r"GroqClient\(api_key=['\"][^'\"]{12,}['\"]\)",
        "GroqClient(api_key=os.environ.get('GROQ_API_KEY', ''))",
    ),
    (
        "check_api_quota.py",
        r"^token\s*=\s*['\"][^'\"]{12,}['\"]",
        "token = os.environ.get('HF_TOKEN', '')",
    ),
    (
        "debug_news.py",
        r"HuggingFaceClient\(api_token=['\"][^'\"]{12,}['\"]\)",
        "HuggingFaceClient(api_token=os.environ.get('HF_TOKEN', ''))",
    ),
    (
        "strategies/news_sentiment_strategy.py",
        r"HuggingFaceClient\(api_token=['\"][^'\"]{12,}['\"]\)",
        "HuggingFaceClient(api_token=os.environ.get('HF_TOKEN', ''))",
    ),
    (
        "test_financial_models.py",
        r"^token\s*=\s*['\"][^'\"]{12,}['\"]",
        "token = os.environ.get('HF_TOKEN', '')",
    ),
    (
        "test_finbert.py",
        r"^token\s*=\s*['\"][^'\"]{12,}['\"]",
        "token = os.environ.get('HF_TOKEN', '')",
    ),
    (
        "test_hf.py",
        r"^token\s*=\s*['\"][^'\"]{12,}['\"]",
        "token = os.environ.get('HF_TOKEN', '')",
    ),
    (
        "test_hf_simple.py",
        r"^token\s*=\s*['\"][^'\"]{12,}['\"]",
        "token = os.environ.get('HF_TOKEN', '')",
    ),
    # ---------- stock_intelligence（父仓库）----------
    (
        "stock_intelligence.py",
        r"FEISHU_APP_ID\s*=\s*os\.environ\.get\(\s*['\"]FEISHU_APP_ID['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)",
        "FEISHU_APP_ID = os.environ.get(\"FEISHU_APP_ID\", \"\")",
    ),
    (
        "stock_intelligence.py",
        r"FEISHU_APP_SECRET\s*=\s*os\.environ\.get\(\s*['\"]FEISHU_APP_SECRET['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)",
        "FEISHU_APP_SECRET = os.environ.get(\"FEISHU_APP_SECRET\", \"\")",
    ),
    (
        "stock_intelligence.py",
        r"FEISHU_RECEIVE_ID\s*=\s*os\.environ\.get\(\s*['\"]FEISHU_RECEIVE_ID['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)",
        "FEISHU_RECEIVE_ID = os.environ.get(\"FEISHU_RECEIVE_ID\", \"\")",
    ),
    (
        "push_feishu.py",
        r"FEISHU_APP_ID\s*=\s*os\.environ\.get\(\s*['\"]FEISHU_APP_ID['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)",
        "FEISHU_APP_ID = os.environ.get(\"FEISHU_APP_ID\", \"\")",
    ),
    (
        "push_feishu.py",
        r"FEISHU_APP_SECRET\s*=\s*os\.environ\.get\(\s*['\"]FEISHU_APP_SECRET['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)",
        "FEISHU_APP_SECRET = os.environ.get(\"FEISHU_APP_SECRET\", \"\")",
    ),
    (
        "push_feishu.py",
        r"FEISHU_RECEIVE_ID\s*=\s*os\.environ\.get\(\s*['\"]FEISHU_RECEIVE_ID['\"]\s*,\s*['\"][^'\"]+['\"]\s*\)",
        "FEISHU_RECEIVE_ID = os.environ.get(\"FEISHU_RECEIVE_ID\", \"\")",
    ),
    (
        "test_feishu.py",
        r"^FEISHU_APP_ID\s*=\s*['\"][^'\"]{8,}['\"]",
        "FEISHU_APP_ID = os.environ.get(\"FEISHU_APP_ID\", \"\")",
    ),
    (
        "test_feishu.py",
        r"^FEISHU_APP_SECRET\s*=\s*['\"][^'\"]{8,}['\"]",
        "FEISHU_APP_SECRET = os.environ.get(\"FEISHU_APP_SECRET\", \"\")",
    ),
    (
        "test_feishu.py",
        r"^FEISHU_RECEIVE_ID\s*=\s*['\"][^'\"]{8,}['\"]",
        "FEISHU_RECEIVE_ID = os.environ.get(\"FEISHU_RECEIVE_ID\", \"\")",
    ),
]

# 需要整份重写的文件（原内容全是凭证，逐行替换没意义）
REWRITE_FILES = {
    "config/joinquant_config.py": '''# -*- coding: utf-8 -*-
"""聚宽 JQData 配置 —— 全部从环境变量读取，不要在这里写死账号密码"""

import os

JOIQUANT_PHONE = os.environ.get("JOINQUANT_PHONE", "")
JOIQUANT_PASSWORD = os.environ.get("JOINQUANT_PASSWORD", "")


def assert_configured():
    if not JOIQUANT_PHONE or not JOIQUANT_PASSWORD:
        raise RuntimeError(
            "缺少聚宽账号配置。请设置环境变量 JOINQUANT_PHONE / JOINQUANT_PASSWORD"
        )
''',
}

# 需要从 git 索引里移除的文件（本地保留，但不再提交）
UNTRACK_FILES = [
    "config/joinquant_config.py",
    "config/tushare_config.py",
    "config/feishu_config.py",
    "push_feishu.py",
]

# --------------------------------------------------------------
# 2. 残留扫描规则
# --------------------------------------------------------------

LEAK_PATTERNS = [
    (r"hf_[A-Za-z0-9]{30,}", "HuggingFace Token"),
    (r"gsk_[A-Za-z0-9]{40,}", "Groq API Key"),
    (r"ghp_[A-Za-z0-9]{30,}", "GitHub PAT"),
    (r"github_pat_[A-Za-z0-9_]{50,}", "GitHub PAT (fine-grained)"),
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI-style Key"),
    (r"\bcli_[a-z0-9]{16,}\b", "飞书 App ID"),
    (r"\b[0-9a-f]{56}\b", "Tushare Token（56 位十六进制）"),
    (r"(?i)(password|passwd|pwd)\s*=\s*['\"][^'\"]{4,}['\"]", "明文密码"),
    (r"\b1[3-9]\d{9}\b", "手机号"),
]

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "data/cache"}
SCAN_EXT = {".py", ".yml", ".yaml", ".json", ".md", ".js", ".html", ".sh", ".ps1", ".txt", ".env"}


def ensure_os_import(text: str) -> str:
    """确保文件顶部 import 了 os"""
    if re.search(r"^\s*import\s+os\s*$", text, re.M):
        return text
    lines = text.split("\n")
    insert_at = 0
    for i, ln in enumerate(lines[:20]):
        if ln.startswith("#") or ln.strip() == "" or ln.startswith('"""') or ln.startswith("'''"):
            insert_at = i + 1
        elif ln.startswith("import ") or ln.startswith("from "):
            insert_at = i
            break
    lines.insert(insert_at, "import os")
    return "\n".join(lines)


def apply_rewrites(root: str, dry_run: bool):
    done = []
    for rel, content in REWRITE_FILES.items():
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            if f.read().strip() == content.strip():
                continue  # 已经处理过
        done.append(rel)
        if not dry_run:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
    return done


def apply_rules(root: str, dry_run: bool):
    changed = []
    for rel, pattern, replacement in RULES:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        new, n = re.subn(pattern, replacement, text, flags=re.M)
        if n == 0:
            continue
        new = ensure_os_import(new)
        changed.append((rel, n))
        if not dry_run:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new)
    return changed


def scan(root: str):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] not in SCAN_EXT:
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root)
            if rel.replace("\\", "/").startswith("scripts/purge_secrets.py"):
                continue  # 跳过本脚本自身
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    for i, line in enumerate(f, 1):
                        for pat, label in LEAK_PATTERNS:
                            if re.search(pat, line):
                                hits.append((rel, i, label, line.strip()[:70]))
            except Exception:
                pass
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只显示，不修改")
    ap.add_argument("--root", default=".", help="仓库根目录")
    ap.add_argument("--scan-only", action="store_true", help="只扫描残留")
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    print("=" * 66)
    print(f"密钥清理  root={root}")
    print("=" * 66)

    if not args.scan_only:
        changed = apply_rules(root, args.dry_run)
        if changed:
            verb = "将修改" if args.dry_run else "已修改"
            print(f"\n[1] {verb} {len(changed)} 处硬编码密钥：")
            for rel, n in changed:
                print(f"      {rel}  ({n} 处)")
        else:
            print("\n[1] 没有找到需要替换的硬编码密钥（可能已经处理过）")

        rewritten = apply_rewrites(root, args.dry_run)
        if rewritten:
            verb = "将整份重写" if args.dry_run else "已整份重写"
            print(f"\n[2] {verb}（原内容全是凭证）：")
            for rel in rewritten:
                print(f"      {rel}")
        else:
            print("\n[2] 没有需要整份重写的文件")

        print("\n[3] 从 git 索引中移除（本地文件保留，只是不再提交）：")
        any_tracked = False
        for rel in UNTRACK_FILES:
            if os.path.exists(os.path.join(root, rel)):
                any_tracked = True
                print(f"      git rm --cached {rel}")
        if not any_tracked:
            print("      （无）")

    print("\n[4] 全仓扫描残留凭证：")
    hits = scan(root)
    if hits:
        for rel, ln, label, snippet in hits:
            masked = re.sub(r"[A-Za-z0-9]{12,}", "<REDACTED>", snippet)
            print(f"      [{label}] {rel}:{ln}")
            print(f"          {masked}")
        print(f"\n    仍有 {len(hits)} 处疑似凭证，请逐条确认。")
        return 1
    print("      干净，没有发现残留凭证。")
    print("\n" + "=" * 66)
    print("下一步：git 历史里的旧密钥仍然存在，见 scripts/purge_git_history.sh")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
