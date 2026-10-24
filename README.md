# fantasy-analysis (ffai)

这是 ESPN 梦幻橄榄球(NFL fantasy)的**阵容分析助手**。
它现在由一个 **Chrome 扩展**和一个**本机 Python 服务**组成。
你点一下按钮,扩展才会读你的 ESPN 联赛并分析。
没有后台程序一直在跑,也不发邮件。
它只读 ESPN 数据。它不会自动改阵容,不会加人,也不会发交易。

完整设计见 [docs/SPEC.md](docs/SPEC.md)。第 0 节是当前的架构。

## 工作方式

```
Chrome 扩展(侧边栏)                       本机服务(Python, 127.0.0.1:8765)
  用你浏览器里已登录的 ESPN 取数据  ──原始 JSON──>  解析,找到你的队伍,检查
  显示分析结果                      <──分析结果──
```

- **扩展不碰 cookie。** 你已经在 Chrome 里登录了 ESPN。扩展发请求时,浏览器会自动带上登录状态。扩展从不读取、保存或发送 `espn_s2`。扩展只读 `SWID`。扩展用 `SWID` 认出哪支队伍是你的。`SWID` 不是登录凭证。
- **分析只在你点按钮时运行。** 打开侧边栏不会请求 ESPN。
- **AI 解释是第二个按钮。** 你点了,扩展才会调用 AI。所以花不花钱由你决定。
- **分析代码只有一份**,在 `ffai/pipeline.py`。以后的后台程序可以直接用它。

## 现在做到哪了

| 部分 | 状态 |
|---|---|
| 解析 ESPN 数据,找到你的队伍,显示阵容 | 已完成 |
| 警告:首发里有人 OUT、轮空或空位 | 已完成 |
| 本机服务,侧边栏界面,AI 解释(Anthropic 和 OpenAI 兼容) | 已完成 |
| 在你真实的 ESPN 登录上验证扩展能取到数据 | **还没验证**,见下面第 3 步 |
| 最优阵容,胜率,自由球员评分 | 未实现。分析结果里会写"还没检查" |
| 后台定时检查,推送,部署到 stock-ai 的同一台 VM | 暂停。先搞清楚 cookie 的规律 |
| 交易建议 | v2,未开始 |

## 使用

### 1. 启动本机服务

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m ffai serve
```

服务只监听 `127.0.0.1:8765`。你可以用 `--port` 改端口。服务不需要 `.env`。

### 2. 加载扩展

1. 打开 `chrome://extensions`,在右上角打开"开发者模式"。
2. 点"加载已解压的扩展程序",选本仓库的 `extension/` 文件夹。
3. 这一步可选。复制扩展的 ID,写进 `.env` 的 `EXTENSION_ID`。服务就只接受这一个扩展。

### 3. 第一次使用

1. 在 Chrome 里登录 ESPN,打开你的联赛页面。
2. 点工具栏上的扩展图标。侧边栏会打开。
3. 点 **From tab**。扩展从当前 ESPN 页面的地址里读出联赛 ID 和队伍 ID。你有两个联赛,就各点一次。点第二次前,先切换到另一个联赛的页面。
4. 点 **Analyze**。成功时,你会看到首发阵容、警告和自由球员。
5. 如果提示 ESPN 返回 401,说明扩展的请求没有带上登录状态。请告诉我。我会改成在 ESPN 页面里发请求。

### 4. AI 解释(可选)

1. 展开 **AI settings**。
2. 选 provider,填 API key 和模型。
3. 点 **Explain with AI**。

Chrome 把 key 保存在这个浏览器配置里,但不加密。
扩展只把 key 发到本机服务。
本机服务把 key 转给 AI 提供商。服务不保存 key,也不写进日志。
请用设了额度上限的 key。

## 测试

```bash
.venv/bin/ruff check --select E9,F63,F7,F82 ffai tests
.venv/bin/pytest tests -q
```

测试不需要网络,也不需要 `.env`。
测试数据是 [espn-api](https://github.com/cwendt94/espn-api) 真实响应的裁剪版。说明见 `tests/fixtures/README.md`。
扩展没有自动化测试。开发时用一个假数据页面手动验证过界面。

## 命令

| 命令 | 作用 | 状态 |
|---|---|---|
| `python -m ffai serve [--port]` | 启动扩展用的本机服务 | 可用 |
| `python -m ffai test-notify` | 往已配置的渠道发测试消息 | 可用(目前只有邮件) |
| `python -m ffai check [--dry-run]`、`run`、`report`、`teams`、`demo` | 后台阶段的命令 | 未实现。命令打印提示,然后以退出码 2 结束 |

## 后台程序(暂停)

后台定时检查和推送要等扩展跑通之后再做。
还要先搞清楚 cookie 的规律。
后台程序会部署在 stock-ai 所在的同一台 GCP VM 上。
它有自己的仓库和自己的 Docker Compose 项目。
部署准备见 [DEPLOY.md](DEPLOY.md)。现在**不要部署**。

## 安全

- `ESPN_S2` 等同于你的 ESPN 登录凭证。只有后台阶段会用到它。把 `.env` 的权限设成 600。不要提交它。不要把它写进日志,也不要贴到聊天里。
- 本机服务只监听 `127.0.0.1`。它只接受来自 Chrome 扩展的请求。
