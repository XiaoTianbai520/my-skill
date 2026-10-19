# 代理不可用时的镜像回退方案

当 `proxy_probe.py` 判定 `PROXY_DOWN`（本机 7890 没在监听）或 `PROXY_UP_BUT_BLOCKED`
（代理上游节点挂了）时，改用国内镜像源。**镜像和代理二选一即可，不要叠加**——
叠加会让本已很快的国内流量绕一圈变慢。

---

## Python / PyPI

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>      # 清华
pip install -i https://mirrors.aliyun.com/pypi/simple/ <pkg>        # 阿里云
pip install -i https://mirrors.cloud.tencent.com/pypi/simple <pkg>  # 腾讯云
```

持久：`pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple`

uv：`UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv pip install <pkg>`
poetry：`poetry source add --priority=primary tsinghua https://pypi.tuna.tsinghua.edu.cn/simple/`

---

## Node / npm

```bash
npm config set registry https://registry.npmmirror.com
pnpm config set registry https://registry.npmmirror.com
yarn config set registry https://registry.npmmirror.com
# 还原
npm config set registry https://registry.npmjs.org
```

二进制包镜像（node-gyp / Electron / Puppeteer 下载慢时的关键）：

```bash
npm config set disturl https://npmmirror.com/dist
export ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
export PUPPETEER_DOWNLOAD_BASE_URL=https://npmmirror.com/mirrors/chrome-for-testing
export SASS_BINARY_SITE=https://npmmirror.com/mirrors/node-sass
```

---

## Git 仓库

| 源 | 镜像 |
|---|---|
| github.com | `https://ghproxy.net/https://github.com/...`（前缀式） |
| github.com | `https://hub.fastgit.xyz/...`（不稳定，备选） |
| raw.githubusercontent | `https://ghproxy.net/https://raw.githubusercontent.com/...` |
| gist | 同上前缀 |

Git 改写成自动走镜像：

```bash
git config --global url."https://ghproxy.net/https://github.com/".insteadOf "https://github.com/"
# 取消
git config --global --unset url."https://ghproxy.net/https://github.com/".insteadOf
```

release 附件下载：把 `github.com/.../releases/download` 换成 `ghproxy.net/https://github.com/...`。

---

## 其他

| 生态 | 镜像 |
|---|---|
| Go | `go env -w GOPROXY=https://goproxy.cn,direct` |
| Docker | `/etc/docker/daemon.json` 加 `"registry-mirrors": ["https://docker.m.daocloud.io","https://mirror.ccs.tencentyun.com"]` |
| Rust crates | `~/.cargo/config.toml` 用 `[source.crates-io] replace-with = "ustc"`（中科大 / rsproxy.cn） |
| Maven | `~/.m2/settings.xml` 配阿里云 `<mirror>`：https://maven.aliyun.com/repository/public |
| Gradle | `init.gradle` 把 `mavenCentral()` 换成 `https://maven.aliyun.com/repository/public` |
| HuggingFace | `export HF_ENDPOINT=https://hf-mirror.com` |
| Conda | 清华/北外 anaconda 镜像，改 `~/.condarc` 的 `channels` |
| Homebrew | `export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles` |
| Ubuntu apt | 换 `mirrors.tuna.tsinghua.edu.cn` / `mirrors.aliyun.com` 源 |

---

## 判定顺序

1. 先跑 `proxy_probe.py`。`PROXY_OK` → 用代理。
2. `PROXY_DOWN` 且目标是**国外**资源 → 用镜像。
3. `PROXY_DOWN` 且目标是**国内**资源（如 npmmirror、阿里云）→ 直连本来就快，
   先排查别的问题（DNS、磁盘、目标站限流），不要盲目加代理或换源。
4. 代理生效但仍慢 → 换代理节点（Clash 里切一个延迟低的），再不行叠加镜像。
