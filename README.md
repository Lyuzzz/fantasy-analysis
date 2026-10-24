# fantasy-analysis (ffai)

ESPN 梦幻橄榄球(NFL fantasy)的**阵容 / 自由球员提醒助手**。它定时检查你的私人联赛,**只有需要你动手的时候才推送**。只读 ESPN 数据,不会自动改阵容、加人或发交易。

完整设计见 [docs/SPEC.md](docs/SPEC.md)。结构沿用我的 stock-ai 项目:定时任务 → 免费的"守门员"检查 → 分析 → (可选)AI 解释 → 推送。

## 现在做到哪了

| 部分 | 状态 |
|---|---|
| 配置、日志、重试、SQLite 去重、邮件推送、CLI、测试、CI、Docker | 已完成 |
| ESPN 客户端和解析(SPEC 第 2 步) | 骨架,未实现 |
| 阵容优化 + 胜率(第 3 步) | 骨架,未实现 |
| 自由球员(第 4 步) | 骨架,未实现 |
| 去重 + 定时 + 健康报警(第 5 步) | 骨架,未实现 |
| AI 解释(第 6 步) | 骨架,未实现 |
| ntfy / Telegram / Discord 推送 | 骨架,未实现 |
| 交易建议、对阵预览(v2) | 未开始 |

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env        # 然后填入配置;.env 已被 .gitignore 排除
.venv/bin/python -m ffai test-notify
```

## 命令

| 命令 | 作用 | 状态 |
|---|---|---|
| `python -m ffai test-notify` | 往每个已配置的渠道发一条测试消息 | 可用(目前只有邮件) |
| `python -m ffai check [--dry-run]` | 跑一次检查 | 未实现 |
| `python -m ffai run` | 常驻循环,每 10 分钟调用一次 `check` | 已接好,等 `check` |
| `python -m ffai report` | 终端打印完整分析 | 未实现 |
| `python -m ffai teams` | 列出所有队伍和 ID | 未实现 |
| `python -m ffai demo` | 用内置假数据跑一遍 | 未实现 |

未实现的命令会提示并以退出码 2 结束。

## 测试

```bash
.venv/bin/ruff check --select E9,F63,F7,F82 ffai tests
.venv/bin/pytest tests -q
```

测试不需要网络,也不需要 `.env`。

## 部署

用 Docker Compose 部署在 GCP VM 上,步骤见 [DEPLOY.md](DEPLOY.md)。

## 安全

`ESPN_S2` 等同于你的 ESPN 登录凭证:`.env` 权限设成 600,不要提交,也不要写进日志。
