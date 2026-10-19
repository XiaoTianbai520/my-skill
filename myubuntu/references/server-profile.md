# MyUbuntu 服务器档案

这是一份从原规范整理出的主机快照，不是实时状态。执行变更前应在服务器上核实。

## 主机与访问

| 项目 | 记录值 |
| --- | --- |
| 默认 SSH 命令 | `ssh myServer` |
| 默认 SSH 登录账户 | `root` |
| 局域网 IPv4 | `192.168.1.102` |
| SSH 端口 | `22/TCP` |
| Tailscale IPv4 | `100.83.74.68` |
| Tailscale IPv6 | `fd7a:115c:a1e0::e92e:4a45` |
| MagicDNS | `linus-stark-nhx0db-de.taild30eeb.ts.net` |

不要把密码、Tailscale Auth Key、一次性授权 URL 或 Jenkins 初始管理员密码写入文档、脚本、仓库或聊天记录。原始规范中的明文密码不属于本 Skill。

## 目录约定

| 类型 | 位置 | 说明 |
| --- | --- | --- |
| 系统与服务配置 | `/etc` | SSH、Nginx 等系统配置 |
| 业务应用 | `/opt/apps/<project>` | Compose 文件、制品、配置和脚本 |
| 中间件 | `/opt/middleware/<service>` | Compose 文件、配置和脚本 |
| 运行环境 | `/opt/runtime` | JDK、Node.js 等 |
| 手动安装工具 | `/opt/tools` | CLI、Java Agent 等 |
| 重要持久化数据 | `/data/<service>` | 数据库、对象存储、上传文件等 |
| 备份 | `/data/backup` | 受限权限；应另存加密副本 |
| 应用日志 | `/var/log/apps` | 业务应用日志 |
| 静态网站 | `/var/www` | 前端构建产物 |
| 开发源码 | `~/Projects` | 开发中的源码，不是部署目录 |

业务容器命名使用 `<project>-<module>`，例如 `huimeng-api`。中间件容器沿用简短稳定名称，例如 `mysql`、`redis`、`rmqnamesrv`、`rmqbroker`、`rmqproxy`、`rmqdashboard`、`skywalking-banyandb`、`skywalking-oap`、`skywalking-ui`、`jenkins` 和 `minio`。

## 服务入口与数据

| 服务 | 地址或端口 | Compose/管理目录 | 主要持久化位置 |
| --- | --- | --- | --- |
| Cockpit | `192.168.1.102:9090` | 系统服务 | 按系统配置 |
| cpolar | `192.168.1.102:9200` | 需实时核实 | 需实时核实 |
| RocketMQ NameServer | `192.168.1.102:9876` | `/opt/middleware/rocketmq` | Compose 配置 |
| RocketMQ Broker | `192.168.1.102:10911` | `/opt/middleware/rocketmq` | `/data/rocketmq/broker/store` |
| RocketMQ Proxy | `192.168.1.102:8081` | `/opt/middleware/rocketmq` | Compose 配置 |
| RocketMQ Dashboard | `http://192.168.1.102:8082/` | `/opt/middleware/rocketmq` | 无关键业务数据 |
| SkyWalking UI | `http://192.168.1.102:18082/` | `/opt/middleware/skywalking` | `/data/skywalking/banyandb` |
| SkyWalking OAP gRPC | `192.168.1.102:11800` | `/opt/middleware/skywalking` | `/data/skywalking/banyandb` |
| SkyWalking OAP HTTP | `192.168.1.102:12800` | `/opt/middleware/skywalking` | `/data/skywalking/banyandb` |
| Nacos Console | `http://192.168.1.102:18080/` | `/opt/middleware/nacos` | `/data/nacos/derby-data` |
| Nacos Server | `192.168.1.102:8848` | `/opt/middleware/nacos` | `/data/nacos/derby-data` |
| Nacos gRPC | `192.168.1.102:9848` | `/opt/middleware/nacos` | `/data/nacos/derby-data` |
| Jenkins | `http://192.168.1.102:18081/` | `/opt/middleware/jenkins` | `/data/jenkins` |
| MySQL | `192.168.1.102:3306` | `/opt/middleware/mysql` | `/data/mysql` |
| Redis | `192.168.1.102:6379` | `/opt/middleware/redis` | 需通过挂载配置核实 |

## 已记录的软件快照

- SkyWalking：BanyanDB `0.10.3`、OAP/UI `10.4.0-java17`；Java Agent `9.7.0` 位于 `/opt/tools/skywalking-java-agent-9.7.0`。
- Jenkins：截至 `2026-09-27`，镜像标签为 `jenkins/jenkins:lts-jdk21`，记录版本 `2.568.3`、Java `21.0.12.1`，容器名 `jenkins`，宿主机端口 `18081` 映射容器 `8080`，Agent 端口 `50000` 未发布。
- Tailscale：截至 `2026-09-27`，记录版本 `1.102.4`，由 `tailscaled.service` 管理，状态目录 `/var/lib/tailscale`。
- Ubuntu：原规范记录为 `26.04`，APT 代号 `resolute`。在使用发行版相关软件源前必须以 `lsb_release -cs` 或 `/etc/os-release` 实时核实。

上述版本和健康状态可能已经变化。不要根据快照直接决定升级、降级或兼容性方案。
