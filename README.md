# fantasy-analysis (ffai)

ESPN 梦幻橄榄球(NFL fantasy)的**阵容分析助手**。目前是一个 **Chrome 侧边栏扩展 + 本机 Python 服务**:你点一下按钮,它才去读你的 ESPN 联赛并分析,没有后台一直在跑,也不发邮件。只读 ESPN 数据,不会自动改阵容、加人或发交易。

完整设计见 [docs/SPEC.md](docs/SPEC.md)(第 0 节是当前架构)。

## 怎么工作的

```
Chrome 扩展(侧边栏)                       本机服务(Python, 127.0.0.1:8765)
  用你浏览器里已登录的 ESPN 取数据  ──原始 JSON──>  解析 → 找到你的队伍 → 检查
  显示结果                          <──分析结果──
```

- **扩展不碰 cookie**:你已经在 Chrome 里登录了 ESPN,扩展发请求时浏览器自动带上登录状态。`espn_s2` 从不被读取、保存或发送。扩展只读 `SWID`(用来认出哪支队伍是你的,它不是登录凭证)。
- **分析只在你点按钮时跑**。打开侧边栏不会请求 ESPN。
- **AI 解释是第二个按钮**,你点了才调用,花不花钱由你决定。
- 分析代码只有一份(`ffai/pipeline.py`),以后后台程序可以直接复用。

## 现在做到哪了

| 部分 | 状态 |
|---|---|
| 解析 ESPN 数据、找到我的队伍、显示阵容 | 已完成 |
| 警告:首发里有人 OUT / 轮空 / 空位 | 已完成 |
| 本机服务、侧边栏界面、AI 解释(Anthropic / OpenAI 兼容) | 已完成 |
| 在你真实的 ESPN 登录上验证扩展能取到数据 | **还没验证,下面第 3 步** |
| 最优阵容、胜率、自由球员评分 | 未实现(结果里会写"还没检查") |
| 后台定时检查 + 推送 + 部署到 stock-ai 同一台 VM | 暂停,等搞清楚 cookie 的规律 |
| 交易建议 | v2,未开始 |

## 使用

### 1. 启动本机服务

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m ffai serve
```

服务只监听 `127.0.0.1:8765`(端口可以用 `--port` 改)。不需要 `.env`。

### 2. 加载扩展

1. 打开 `chrome://extensions`,右上角打开"开发者模式"。
2. 点"加载已解压的扩展程序",选本仓库的 `extension/` 文件夹。
3. (可选)复制扩展的 ID,写进 `.env` 的 `EXTENSION_ID`,服务就只接受这一个扩展。

### 3. 第一次使用

1. 在 Chrome 里登录 ESPN,打开你的联赛页面。
2. 点工具栏上的扩展图标,侧边栏会打开。
3. 点 **From tab**,它会从当前 ESPN 页面地址里读出联赛 ID 和队伍 ID。两个联赛就各点一次(切换到另一个联赛的页面再点)。
4. 点 **Analyze**。成功的话会看到你的首发阵容、警告和自由球员。
5. 如果提示 ESPN 返回 401,说明扩展的请求没有带上登录状态。这种情况请告诉我,我会改成在 ESPN 页面里发请求。

### 4. AI 解释(可选)

展开 **AI settings**,选 provider,填 API key 和模型,然后点 **Explain with AI**。key 保存在这个 Chrome 配置里(Chrome 不加密),只会发到本机服务,再由它转给 AI 提供商,服务不保存也不写日志。建议用设了额度上限的 key。

## 测试

```bash
.venv/bin/ruff check --select E9,F63,F7,F82 ffai tests
.venv/bin/pytest tests -q
```

测试不需要网络,也不需要 `.env`。测试数据是 [espn-api](https://github.com/cwendt94/espn-api) 的真实响应裁剪版,见 `tests/fixtures/README.md`。扩展没有自动化测试,界面部分我用测试页面手动验证过。

## 命令

| 命令 | 作用 | 状态 |
|---|---|---|
| `python -m ffai serve [--port]` | 启动扩展用的本机服务 | 可用 |
| `python -m ffai test-notify` | 往已配置的渠道发测试消息 | 可用(目前只有邮件) |
| `python -m ffai check [--dry-run]` / `run` / `report` / `teams` / `demo` | 后台阶段的命令 | 未实现,提示后以退出码 2 结束 |

## 后台部分(暂停)

后台定时检查和推送要等扩展跑通、搞清楚 cookie 的规律之后再做,到时会和 stock-ai 部署在同一台 GCP VM 上(各自独立的仓库和 Docker Compose 项目)。部署准备见 [DEPLOY.md](DEPLOY.md),现在**不要部署**。

## 安全

- `ESPN_S2` 等同于你的 ESPN 登录凭证(只在后台阶段才会用到):`.env` 权限设成 600,不要提交,也不要写进日志或贴到聊天里。
- 本机服务只监听 `127.0.0.1`,并且只接受来自 Chrome 扩展的请求。
