# 校验脚本

这些脚本用于验证规则正确性、搜索等价性和性能提升。全部只用标准库 + Pillow（仅 GUI 冒烟需要）。

## 路径约定

脚本假设自己位于**仓库根目录下的 `verification/`**，并通过

```text
../五子棋桌面版
```

找到桌面版引擎与界面。因此请保持目录结构，或在运行前把 `五子棋桌面版/` 放到同级。

```powershell
cd verification
python test_rules.py
```

## 脚本说明

| 脚本 | 作用 | 依赖 / 备注 |
| --- | --- | --- |
| `test_rules.py` | 17 项规则表驱动用例：边线/角落/居中成五、长连、双四、双三、五连优先、满盘等 | 使用桌面版当前 `engine.py` |
| `run_rules_v2.py` | 用同一套规则用例测试 `engine_v2.py` | 便于对照 |
| `compare.py` | 新旧引擎逐项差分：`analyze_move` / `is_legal_move` / `winning_line_for` / `would_win_at` / `placement_score` / `_quick_point_score` / `get_candidates` / `evaluate_board`，共 75,912 个“空点 × 执子方”组合 | 使用本目录的 `engine_v1.py`、`engine_v2.py` |
| `root_compare.py` | 12 个局面 × 10 个根着法，固定深度 3 的根评分差分 | 期望 0 差异 |
| `test_ctx.py` | 增量搜索上下文 fuzz：随机落子/悔棋后，`win_sets`、邻居计数、Zobrist 哈希与全量重算对比 | 期望 0 差异 |
| `tactics.py` | AI 战术用例：自己成五、挡对方四、黑棋落点合法 | 简单难度按设计会随机放水 |
| `match.py` | 新旧引擎自对弈（默认每步 0.25 秒，8 局） | 约 1–2 分钟 |
| `smoke_gui.py` | 无人工点击的 Tk 流程冒烟：双人落子/悔棋、人机应手、困难模式重开取消 | 需要桌面会话 |
| `final_bench.py` | 新旧引擎微基准 + 固定深度 4 搜索 + 中等难度耗时 | 约 30 秒 |
| `hard_compare.py` | 真实 1.15 秒预算下的节点数，以及迭代加深各层耗时 | 约 30 秒 |
| `fixed_depth.py` | 固定深度 3/4 的纯搜索耗时对比，不设时间限制 | 较慢 |
| `ab_score.py` | A/B 两种 `_quick_point_score` 实现的单点耗时与校验和 | 约 10 秒 |
| `patterns.py` | 穷举单方向局部的四/三数量 | 约 10 秒 |
| `multiplicity.py` | 穷举 11 格窗口，验证“单方向最多 1 个三、可以有 2 个四” | 约 10 秒 |

## 期望结果（参考）

- `test_rules.py`：`0 failure(s)`
- `compare.py`：`checked_cells=75912 problems=0`
- `root_compare.py`：`root evaluations=120 mismatches=0`
- `test_ctx.py`：`failures=0`
- `final_bench.py`：固定深度 4 约 **6.6×**，禁手判定约 **14×**（具体数值随机器负载浮动，倍率比绝对值可靠）
- `hard_compare.py`：同一 1.15 秒预算，新版节点数约为旧版 **5–6 倍**

## 说明

- 脚本里的 `engine_v1.py` / `engine_v2.py` 是**代码副本**，用于差分和对照；桌面版实际运行的是 `../五子棋桌面版/engine.py`。
- 性能数据受后台负载影响，请以同一进程内的倍率为准。
- 这些脚本不会修改桌面版文件；`smoke_gui.py` 会短暂创建 Tk 窗口并自动关闭。
