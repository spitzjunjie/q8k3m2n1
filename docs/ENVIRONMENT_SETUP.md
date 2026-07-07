# 环境配置指南

## 概述

本项目包含敏感信息（API密钥、收益数据），已配置 `.gitignore` 保护本地文件不被上传。

## 需要保护的敏感文件

| 文件 | 内容 | 状态 |
|------|------|------|
| `config/tushare_config.py` | Tushare Token | 已忽略 |
| `config/feishu_config.py` | 飞书App Secret | 已忽略 |
| `output/strategy_data.json` | 收益数据 | 已忽略 |
| `output/backtest_history.json` | 回测历史 | 已忽略 |

## 本地配置方法

### 1. 创建配置文件

```bash
# 复制示例配置文件
cp config/tushare_config.py.example config/tushare_config.py
```

### 2. 设置环境变量（推荐）

#### Windows PowerShell
```powershell
$env:TUSHARE_TOKEN = "你的Tushare Token"
```

#### Linux/Mac
```bash
export TUSHARE_TOKEN="你的Tushare Token"
```

#### 持久化配置（Windows）
将以下内容添加到 `~/.bashrc` 或创建 `config/local_env.ps1`：

```powershell
# config/local_env.ps1
$env:TUSHARE_TOKEN = "你的Tushare Token"
```

### 3. GitHub Actions 配置

在 GitHub 仓库 Settings → Secrets 中添加：

| Name | Value |
|------|-------|
| `TUSHARE_TOKEN` | 你的Tushare Token |
| `FEISHU_APP_ID` | 飞书App ID |
| `FEISHU_APP_SECRET` | 飞书App Secret |

## 架构说明

```
┌─────────────────────────────────────────────────────┐
│  本地开发环境                                        │
├─────────────────────────────────────────────────────┤
│  config/tushare_config.py    ← 包含真实Token（不上传）│
│  config/tushare_config.py.example ← 模板（公开）     │
└─────────────────────────────────────────────────────┘
                        ↓ git push
┌─────────────────────────────────────────────────────┐
│  GitHub 仓库                                        │
├─────────────────────────────────────────────────────┤
│  .gitignore                 ← 过滤敏感文件            │
│  config/tushare_config.py   ← 不存在（被过滤）       │
│  config/tushare_config.py.example ← 存在（模板）    │
└─────────────────────────────────────────────────────┘
                        ↓ GitHub Actions
┌─────────────────────────────────────────────────────┐
│  GitHub Actions                                     │
├─────────────────────────────────────────────────────┤
│  Secrets.TUSHARE_TOKEN       ← 从Settings读取        │
│  Secrets.FEISHU_APP_SECRET  ← 从Settings读取        │
└─────────────────────────────────────────────────────┘
```

## 安全检查

上传前，运行以下命令确认没有敏感文件：

```bash
# 检查将被上传的文件
git status

# 检查特定文件
cat config/tushare_config.py
```

如果输出包含真实Token，请确保：
1. 该文件在 `.gitignore` 中
2. `git status` 显示该文件为 "untracked" 或被忽略
