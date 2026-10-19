---
name: slow-download-fix
description: 解决下载慢、下载卡住、连接超时、包管理器拉不动依赖的问题。当 pip / npm / pnpm / yarn / git clone / curl / wget / go / cargo / maven / gradle / docker / HuggingFace / conda 等下载缓慢、stall、timeout、ConnectionReset、SSL 握手失败，或用户提到「下载慢、装不上、拉不动、太慢了、超时、走代理、加速、换个源」时使用。自动接入本机代理 http://127.0.0.1:7890 并验证提速效果；代理不可用时回退到国内镜像源。This skill should be used whenever any download, install, clone, fetch, or package-manager operation is slow, stalls, or times out.
agent_created: true
---

# 下载加速

本机有一个本地代理（Clash / Mihomo 类）监听在 `127.0.0.1:7890`。遇到下载慢的问题时，
优先把它接上，而不是让用户干等或反复重试。

## 默认配置（不要问用户，直接用）

| 项 | 值 |
|---|---|
| 代理地址 | `http://127.0.0.1:7890` |
| 协议 | `http://`（**不是** https；Clash 的 mixed port 用明文协商 CONNECT） |
| NO_PROXY | `localhost,127.0.0.1,::1,.cn,mirrors.aliyun.com,registry.npmmirror.com` |

## 工作流

### 第 1 步：探活，别瞎试

不要先假设代理活着。跑一次探测，拿到明确结论：

```bash
python ~/.workbuddy/skills/slow-download-fix/scripts/proxy_probe.py --compare
```

按退出码分诊：

- `0` / `PROXY_OK` → 代理可用，进第 2 步。`--compare` 给出的 `Speedup` 若 ≥1.2x，说明代理确实更快。
- `2` / `PROXY_DOWN` → 7890 没在监听。提示用户打开代理客户端并确认端口，
  **同时**直接进第 3 步走镜像，不要卡在这里等用户。
- `3` / `PROXY_UP_BUT_BLOCKED` → 代理在但上游不通。让用户切节点；本期任务走镜像。

### 第 2 步：接上代理

按正在下载的工具选对应写法，完整矩阵见 `references/tool-proxy-matrix.md`。最高频的几条：

```bash
# pip
pip install --proxy http://127.0.0.1:7890 <pkg>

# npm / pnpm / yarn
npm config set proxy http://127.0.0.1:7890 && npm config set https-proxy http://127.0.0.1:7890

# git（单次，不写进全局配置）
git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 clone <url>

# 任意命令，临时注入环境变量
python ~/.workbuddy/skills/slow-download-fix/scripts/run_with_proxy.py -- <cmd>
```

优先用**单次生效**的方式（命令级 flag、`run_with_proxy.py`），避免污染用户全局环境。
只有在用户明确要求「以后都走代理」时才写持久配置（`pip config set` / `git config --global`）。

### 第 3 步：代理不行就换镜像

完整镜像表见 `references/mirrors.md`。最高频的几条：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>
npm config set registry https://registry.npmmirror.com
go env -w GOPROXY=https://goproxy.cn,direct
git config --global url."https://ghproxy.net/https://github.com/".insteadOf "https://github.com/"
```

**代理和镜像二选一，不要同时开**——叠加会让本来很快的国内流量绕远路变慢。
配了镜像就把 NO_PROXY 里加上对应域名，或把代理取消掉。

### 第 4 步：验证

下载完成后确认真的变快了，而不是「看起来在跑」：

```bash
python ~/.workbuddy/skills/slow-download-fix/scripts/proxy_probe.py
curl -x http://127.0.0.1:7890 -s -o /dev/null -w "%{http_code} %{time_total}s\n" https://registry.npmjs.org/-/ping
```

## 关键判断

- **目标是国内资源时不要加代理**（npmmirror、阿里云、清华源本身就在国内）。
  这类情况下载慢多半是别的原因：DNS、磁盘满、目标站限流、公司网络策略。
- **Docker / apt / yum 走的是系统级代理**，shell 里 export 环境变量没用，
  必须改 `/etc/apt/apt.conf.d/` 或 docker daemon 配置。详见参考文档。
- **不要无脑重试**。同一个命令卡住两次以上，说明是网络路径问题，重试只是浪费时间。
- **大文件 / 大仓库先想别的办法**：`git clone --depth 1`、只下需要的 wheel、
  用 `aria2c -x 16` 多线程，往往比调代理更有效。
- 代理地址写错成 `https://127.0.0.1:7890` 会导致握手失败——这是最常见的低级错误。

## 参考文件

- `references/tool-proxy-matrix.md` — pip/npm/git/go/cargo/maven/docker/curl 等逐工具代理写法
- `references/mirrors.md` — 各生态国内镜像源与回退判定顺序
- `scripts/proxy_probe.py` — 代理探活 + 实测吞吐量，支持 `--compare` / `--json`
- `scripts/run_with_proxy.py` — 临时给单条命令注入代理环境变量
