# MyUbuntu 运维方法

## 通用 Compose 流程

在 `<service-dir>` 替换为档案中的实际目录。先确认当前目录和 Compose 配置：

```bash
cd <service-dir>
pwd
docker compose config --quiet
docker compose ps
```

常用操作：

```bash
docker compose up -d
docker compose stop
docker compose restart
docker compose ps
docker compose logs --tail 100 <service>
```

`docker compose down` 会删除容器和 Compose 网络，通常不会删除宿主机绑定挂载的数据，但必须先用 `docker compose config` 核实挂载。不要添加 `-v`，除非用户明确要求删除命名卷并理解影响。

操作后检查 `docker compose ps`、容器健康状态、最近日志和服务端点。不要仅凭命令退出码断言业务已恢复。

## RocketMQ

目录：`/opt/middleware/rocketmq`。关键容器包括 `rmqnamesrv`、`rmqbroker`、`rmqproxy`、`rmqdashboard`。Broker 数据记录在 `/data/rocketmq/broker/store`。

Dashboard 单独管理：

```bash
cd /opt/middleware/rocketmq
docker compose up -d --no-deps dashboard
docker compose stop dashboard
docker compose restart dashboard
docker compose ps dashboard
docker logs --tail 100 rmqdashboard
```

验证：

```bash
curl -I http://192.168.1.102:8082/
curl -sS http://192.168.1.102:8082/cluster/list.query
```

页面预期返回 HTTP 200；集群接口应成功并能看到 Broker。Dashboard 只应向可信设备开放。配置备份记录为 `/opt/middleware/rocketmq/docker-compose.yml.pre-dashboard`，使用前先确认存在且仍对应当前版本。

## Nacos、MySQL 与 Redis

- Nacos：`/opt/middleware/nacos`；容器 `nacos`；数据 `/data/nacos/derby-data`；日志记录在 `/var/log/nacos`。
- MySQL：`/opt/middleware/mysql`；容器 `mysql`；数据 `/data/mysql`。
- Redis：`/opt/middleware/redis`；容器 `redis`；执行删除容器或升级前先核实实际卷挂载、持久化模式和备份。

分别在其 Compose 目录使用通用流程。数据库服务重启或升级前应确认业务停机窗口、数据备份和恢复方法。

## SkyWalking

目录：`/opt/middleware/skywalking`。记录容器为 `skywalking-banyandb`、`skywalking-oap`、`skywalking-ui`，数据在 `/data/skywalking/banyandb`。

```bash
cd /opt/middleware/skywalking
docker compose config --quiet
docker compose up -d --wait
docker compose ps
docker logs --tail 100 skywalking-oap
curl -fsS http://192.168.1.102:12800/healthcheck
curl -I http://192.168.1.102:18082/
```

Java 应用必须显式附加 Agent。示例中的服务名和 JAR 路径必须替换：

```bash
export SW_AGENT_NAME=<service-name>
export SW_AGENT_COLLECTOR_BACKEND_SERVICES=192.168.1.102:11800
java -javaagent:/opt/tools/skywalking-java-agent-9.7.0/skywalking-agent.jar \
  -jar /opt/apps/<project>/<application>.jar
```

容器化应用需要把 Agent 挂载进容器并使用容器内路径。每个服务使用独立的 `SW_AGENT_NAME`。接入后产生真实请求，再检查服务、JVM 指标和链路。

## Jenkins

目录：`/opt/middleware/jenkins`；容器 `jenkins`；数据 `/data/jenkins`。首次创建数据目录时，记录的容器 UID/GID 是 `1000:1000`，应先用实际镜像核实。

检查：

```bash
cd /opt/middleware/jenkins
docker compose config --quiet
docker compose ps
docker stats --no-stream jenkins
docker logs --tail 100 jenkins
curl -sSI http://192.168.1.102:18081/login
docker exec jenkins java -version
```

只有全新实例首次初始化时才读取 `/var/jenkins_home/secrets/initialAdminPassword`，并避免将输出记录到聊天或仓库。原规范记录 Jenkins 根 URL 曾误设为 `http://192.168.1.102:18081/instance/`，实际直接入口为根路径；修改前先核实当前配置与是否存在反向代理或 `--prefix`。

升级或关键配置变更前：停止 Jenkins；把 `/data/jenkins` 备份到权限受限的位置；验证归档非空、可读取并生成 SHA-256；确保失败时能重新启动旧实例。备份包含密钥和凭据，且本机备份不能防范整机故障。恢复会覆盖数据，必须再次备份现状并获得用户明确确认。

## Tailscale

由 `tailscaled.service` 管理：

```bash
systemctl status tailscaled --no-pager
tailscale status
tailscale ip -4
tailscale ip -6
tailscale netcheck
```

若当前 SSH 会话通过 Tailscale 建立，在执行 `systemctl restart tailscaled`、`tailscale down`、`tailscale logout` 或升级之前，必须确认局域网 SSH、Cockpit、物理控制台或其他带外通道确实可用。`tailscale logout` 会使现有登录失效并需要重新授权。

安装或更新官方 APT 源时，从 `/etc/os-release` 获取当前代号，使用 Tailscale 官方文档提供的对应仓库，并校验下载内容和签名密钥。原规范中的 `resolute` 与固定指纹只是历史快照，不能在未实时核实官方信息时照搬。授权 URL 与 Auth Key 不得写入文档或日志。

## 网络暴露与代理

- 使用 `ss -lntup`、防火墙规则和 Compose 端口映射共同核实监听范围。
- 管理端口优先绑定局域网地址或通过 Tailscale 访问。
- 只有服务器本机确实在 `127.0.0.1:7890` 监听时，服务器命令才能使用该代理。客户端自己的 `127.0.0.1` 不是服务器或容器的回环地址。
- 代理优先设置为单条命令的临时参数，不要未经请求永久写入服务配置。

## 高风险边界

以下动作需要先展示准确目标、影响、备份/回滚路径，并获得明确确认：删除 `/data` 下任何目录；使用 `docker compose down -v`；Docker prune；覆盖恢复；修改 SSH 认证或防火墙导致现有访问变化；注销 Tailscale；公开管理端口；升级数据库、Jenkins 或中间件的主要版本。
