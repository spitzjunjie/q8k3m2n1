---

# 版本记录 v1.1.0

**发布日期**: 2026-07-11
**版本号**: v1.1.0
**状态**: ✅ 已验证

---

## v1.1.0 更新内容

### 核心改进

| 改进项 | 内容 |
|--------|------|
| **止盈止损风控** | 止损-5%，止盈+10%，最大持仓10天 |
| **策略优化** | 趋势跟踪替代追涨策略 |
| **Dashboard修复** | 夏普计算只包含有效数据 |
| **新策略** | 价值动量、高股息、北向重仓、业绩预增 |

### 风控模块

```python
STOP_LOSS = -5      # 止损线：亏损超过5%自动卖出
TAKE_PROFIT = 10    # 止盈线：盈利超过10%自动卖出
MAX_HOLD_DAYS = 10  # 最大持仓天数
```

### 策略分类表现

| 分类 | 均收益 | 说明 |
|------|--------|------|
| 逆向 | +0.99% | 最佳，回调市场有效 |
| 短线事件 | +0.45% | 良好，事件驱动有效 |
| 短线技术 | -1.78% | 仍需优化 |

---

## v1.0.0

**发布日期**: 2026-07-07

### 初始版本

- 45个策略
- AKShare数据源
- Dashboard可视化

---

## 版本概述

这是一个完整的A股多策略量化交易系统，包含选股、择时、回测、评估和可视化功能。

---

## 核心功能

| 模块 | 功能 | 状态 |
|------|------|------|
| **选股策略** | 35个策略（趋势、事件、财务、技术等） | ✅ |
| **择时引擎** | 均线、RSI、MACD、KDJ等技术指标 | ✅ |
| **回测系统** | 历史回测，支持T+1规则 | ✅ |
| **评估体系** | 多维度评分（收益、夏普、最大回撤、胜率） | ✅ |
| **可视化** | Dashboard展示（策略总览、评估中心、详情页） | ✅ |

---

## 技术架构

### 数据层

| 数据源 | 用途 | 稳定性 |
|--------|------|--------|
| **Tushare Pro** (2000积分) | 日线行情、财务数据 | ✅ 稳定 |
| **AKShare** | 备用数据源 | ⚠️ 不稳定（已知） |

### 核心模块

```
stock_intelligence/
├── strategies/          # 35个选股策略
├── timing/             # 择时引擎
├── trading/            # 交易模拟器
├── data/              # 数据获取和缓存
├── config/            # 配置文件
└── output/            # 回测结果输出
```

---

## 验证结果

### 代码审查 (TRAE-code-review)
- ✅ Minor问题1: validate_price_data添加dropna后空数据检查
- ✅ Minor问题2: json_serializer添加datetime类型处理

### 数据验证 (data-validator)
```
✅ Tushare连接 - 通过
✅ 回测文件验证 - 通过
✅ AKShare测试 - INFO（不稳定是正常的）
```

### 回测结果 (30天)
| 指标 | 值 |
|------|-----|
| 策略数量 | 35 |
| 回测区间 | 2026-05-26 ~ 2026-07-07 |
| A级策略 | 3个（多周期共振、高管增持、均线多头排列） |
| 最高收益 | +26.29% |

---

## GitHub Actions

| 任务 | 触发时间 | 说明 |
|------|----------|------|
| **多策略回测** | 每周一到周五 18:30 | 收盘后选股，推送结果 |
| **Deploy to GitHub Pages** | 代码推送后 | 部署Dashboard到GitHub Pages |

**Dashboard地址**: https://spitzjunjie.github.io/multi-strategy-trading/

---

## 目录结构

```
multi-strategy-trading/
├── .github/
│   └── workflows/
│       ├── backtest.yml      # 每日回测定时任务
│       └── deploy.yml       # GitHub Pages部署
├── strategies/               # 选股策略
│   ├── base.py              # 策略基类
│   ├── technical_strategies.py  # 技术指标策略
│   ├── event_strategies.py  # 事件驱动策略
│   ├── factor_strategies.py # 因子策略
│   └── special_strategies.py # 特殊策略
├── timing/
│   └── timing.py            # 择时引擎
├── trading/
│   └── simulator.py         # 交易模拟器
├── data/
│   ├── akshare_helper.py    # AKShare数据封装
│   └── cache/               # 数据缓存
├── config/
│   └── tushare_config.py    # Tushare配置
├── output/
│   ├── strategy_data.json   # 策略数据
│   └── backtest_history.json # 回测历史
├── index.html              # 策略总览
├── evaluation.html          # 策略评估中心
├── detail.html             # 策略详情页
├── backtest.py             # 单次回测脚本
├── backtest_history.py     # 历史回测脚本
├── data_validator.py       # 数据验证模块
├── generate_report.py      # 报告生成器
└── requirements.txt        # Python依赖
```

---

## 已知问题和限制

| 问题 | 说明 | 状态 |
|------|------|------|
| AKShare不稳定 | 东方财富反爬策略导致 | 已知，使用Tushare作为主数据源 |
| 历史回测需本地运行 | GitHub Actions有限时 | 正常设计 |

---

## 下一步可优化方向

1. **策略自动淘汰** - 根据评级自动淘汰D级策略
2. **信号推送** - 微信/邮件通知选股结果
3. **Dashboard增强** - 更多图表和可视化
4. **实盘对接** - 对接券商API（需要账户权限）

---

## 联系方式

- **GitHub仓库**: https://github.com/spitzjunjie/multi-strategy-trading
- **Dashboard**: https://spitzjunjie.github.io/multi-strategy-trading/

---

## 更新日志

### v1.0.2 (2026-07-09)
**上线3个新策略到Dashboard**
- ✅ 南向资金: 10笔交易, -1.68%收益, 胜率35.6%
- ✅ 北向资金: 10笔交易, -1.68%收益, 胜率35.6%
- ✅ 龙虎榜: 10笔交易, -4.45%收益, 胜率42.0%

**未上线策略（无交易）**
- ❌ 量价齐升、资金流事件、研报推荐、业绩暴增
- ❌ 短线动量、ETF二八轮动、反过度自信、超跌反弹、财务基本面过滤小市值

### v1.0.1 (2026-07-08)
- 优化策略选股逻辑
- 修复回测中的数据获取问题

### v1.0.0 (2026-07-07)
- 完成基础框架搭建
- 实现32个选股策略
- 实现择时引擎
- 实现回测系统
- 实现评估体系
- 集成Tushare Pro数据源
- 创建Dashboard可视化界面
- 配置GitHub Actions定时任务
- 完成代码审查和数据验证
