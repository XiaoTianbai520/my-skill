# 各工具接入代理速查表

默认代理地址：`http://127.0.0.1:7890`（下文统一用 `$PROXY` 指代）。
用 `scripts/run_with_proxy.py -- <cmd>` 可临时为任意命令注入代理环境变量，不污染全局。

---

## 0. 通用环境变量（覆盖大部分工具）

```bash
export HTTP_PROXY=$PROXY HTTPS_PROXY=$PROXY ALL_PROXY=$PROXY
export NO_PROXY=localhost,127.0.0.1,::1,.cn,mirrors.aliyun.com,registry.npmmirror.com
```

Windows PowerShell（仅当前会话）：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7890"; $env:HTTPS_PROXY="http://127.0.0.1:7890"
```

Windows 持久化（用户级，重启终端后仍生效）：

```powershell
[Environment]::SetEnvironmentVariable("HTTP_PROXY","http://127.0.0.1:7890","User")
[Environment]::SetEnvironmentVariable("HTTPS_PROXY","http://127.0.0.1:7890","User")
```

> 注意：代理地址要写 `http://`，**不要**写 `https://`。Clash/Mihomo 的 mixed port 对 CONNECT 请求本身就是明文协商。

---

## 1. Python 生态

| 工具 | 命令 |
|---|---|
| pip（临时） | `pip install --proxy http://127.0.0.1:7890 <pkg>` |
| pip（持久） | `pip config set global.proxy http://127.0.0.1:7890` |
| pip（查看/清除） | `pip config list` / `pip config unset global.proxy` |
| uv | `UV_HTTP_PROXY=$PROXY uv pip install <pkg>`，或 `uv pip install --proxy $PROXY` |
| poetry | `POETRY_HTTP_PROXY=$PROXY poetry install` |
| conda | `conda config --set proxy_servers.http $PROXY` + `--set proxy_servers.https $PROXY` |
| conda（取消） | `conda config --remove-key proxy_servers` |
| HuggingFace | `HF_ENDPOINT=https://hf-mirror.com`（见 mirrors.md）+ `HTTPS_PROXY=$PROXY` |
| torchvision / torch hub | 走 `HTTP_PROXY` 环境变量即可 |

pip 持久配置也可直接写入文件：
- Windows：`%APPDATA%\pip\pip.ini`
- Linux/macOS：`~/.config/pip/pip.conf`

```ini
[global]
proxy = http://127.0.0.1:7890
timeout = 60
retries = 5
```

---

## 2. Node 生态

```bash
npm config set proxy    http://127.0.0.1:7890
npm config set https-proxy http://127.0.0.1:7890
npm config delete proxy          # 取消
npm config get proxy             # 查看

yarn config set proxy http://127.0.0.1:7890
yarn config set https-proxy http://127.0.0.1:7890

pnpm config set proxy http://127.0.0.1:7890
pnpm config set https-proxy http://127.0.0.1:7890
```

临时单次：`npm install --proxy $PROXY --https-proxy $PROXY`

> Electron / node-gyp / puppeteer 等会额外下载二进制包，需要同时设置
> `ELECTRON_MIRROR`、`PUPPETEER_DOWNLOAD_BASE_URL`（见 mirrors.md）。

---

## 3. Git

```bash
# 单次（推荐，不写进配置）
git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 clone <url>

# 持久
git config --global http.proxy  http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 只对 GitHub 生效（避免拖慢国内仓库）
git config --global http.https://github.com.proxy http://127.0.0.1:7890

# 取消
git config --global --unset http.proxy
git config --global --unset https.proxy
```

git 走 socks5：`git config --global http.proxy socks5://127.0.0.1:7890`

配合浅克隆大幅提速：
`git clone --depth 1 --filter=blob:none <url>`

---

## 4. 系统与包管理器

| 工具 | 配置 |
|---|---|
| curl | `curl -x http://127.0.0.1:7890 <url>` 或 `export https_proxy=$PROXY` |
| wget | `wget -e use_proxy=yes -e http_proxy=$PROXY -e https_proxy=$PROXY <url>` |
| apt (Debian/Ubuntu) | `Acquire::http::Proxy "http://127.0.0.1:7890";` 写入 `/etc/apt/apt.conf.d/01proxy` |
| yum/dnf (RHEL) | 在 `/etc/yum.conf` 加 `proxy=http://127.0.0.1:7890` |
| Go | `export GOPROXY=https://goproxy.cn,direct` + `HTTPS_PROXY=$PROXY` |
| Rust/cargo | `export HTTPS_PROXY=$PROXY`；或 `~/.cargo/config.toml` 加 `[http] proxy = "..."` |
| Maven | `~/.m2/settings.xml` 的 `<proxies>` 节点；或 `MVN_OPTS="-Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7890"` |
| Gradle | `~/.gradle/gradle.properties`：`systemProp.https.proxyHost=127.0.0.1` / `systemProp.https.proxyPort=7890` |
| Docker daemon | `/etc/systemd/system/docker.service.d/http-proxy.conf` 设 `Environment="HTTPS_PROXY=..."` |
| docker pull | 走 daemon 代理，不是 shell 环境变量 |
| Ruby gem | `gem install --http-proxy $PROXY <gem>` |
| PHP composer | `export HTTP_PROXY=$PROXY` 即可，或 `composer config -g http-proxy $PROXY` |

---

## 5. 验证是否真的生效

```bash
curl -x http://127.0.0.1:7890 -s -o /dev/null -w "%{http_code} %{time_total}s\n" https://www.google.com
python scripts/proxy_probe.py --compare
```

若返回码非 200 或耗时未下降，转 mirrors.md 走镜像方案。
