---
name: java-standards
description: 基于 oneCoupon 项目提炼的 Java 后端开发规范。编写、修改、重构或审查 Java/Spring Boot 代码时使用，尤其涉及 Controller/Service/Mapper 分层、DTO/DO 命名、MyBatis-Plus、统一响应与异常、租户隔离、Redis、RocketMQ、幂等和事务时。用户说“按项目规范写”“补一个接口”“检查 Java 代码规范”也应使用。适用于 oneCoupon 及希望沿用其风格的 Java 服务；迁移到其他仓库时先适配当地约定。不用于纯前端、非 Java 代码或仅讲解 Java 基础语法的任务。
---

# Java 后端开发规范

把需求落实为符合所在仓库风格、能够验证的 Java 改动。此规范源自 oneCoupon 的构建配置和跨模块代码样本；它不是阿里巴巴规范等外部标准的完整实现。

## 1. 先定位，再改动

1. 阅读目标仓库的 `AGENTS.md`、根/模块 `pom.xml`、格式化配置和同模块相邻实现，确认技术版本、包名前缀、现成组件与用户已有改动。
2. 在 oneCoupon 中读取 [项目依据与差异](references/onecoupon-evidence.md)，按表定位实现。其他仓库先适配包名、模块、返回封装及异常体系；不要直接引入 `com.nageoffer` 或固定升级到样本版本。
3. 普通接口读取 [分层与编码](references/layers-and-style.md)；涉及数据、缓存、库存、消息、任务和异步时再读取 [数据与一致性](references/data-and-consistency.md)。
4. 选择现有调用链上的最小改动，复用项目组件。不要因为样本有责任链、分库分表或 Redis，就给简单业务强加这些设施。
5. 修改前判断验证命令是否会改写源码、访问共享中间件或执行数据生成器；遵循文末验证流程。

## 2. 规则的依据与取舍

- **明确配置**：Java 版本、模块边界、依赖管理和已有协议以目标仓库的有效配置为准。格式化文件存在不等于插件已启用它。
- **重复惯例**：在 oneCoupon 中沿用 Controller → Service 接口 → ServiceImpl → Mapper 的组织、构造器注入、ReqDTO/RespDTO/DO 命名、中文业务说明、`Result<T>` 与 `Results.success()`。
- **改进建议**：参数边界、条件更新、异常重试、事务提交时机等补足项要解释原因，不能称为项目已经保证的行为。
- **冲突处理**：用户当前要求优先；随后遵守适用的仓库指令和有效配置，再参考相邻代码。发现旧文档、演示代码、注释占位与实际实现冲突时，核对执行代码并标明差异。
- **迁移边界**：保留目标仓库已经约定的 `Date`/`LocalDateTime`、ID 表示和 JSON 协议；不为统一风格无故改变公开接口。不要复制原作者、宣传链接、历史开发日期、固定用户或项目版权文本到新项目。

## 3. 默认编码决策

| 事项 | 决策 |
| --- | --- |
| 包组织 | `controller`、`service`、`service.impl`、`dao.entity`、`dao.mapper`、`dto.req`、`dto.resp`、`common.constant/enums/context`、`config`、`mq.base/event/producer/consumer`、`toolkit`；只创建需要的包 |
| 类型与命名 | 类型 UpperCamelCase；成员/方法 lowerCamelCase；常量 UPPER_SNAKE_CASE；遵循 `XxxReqDTO`、`XxxRespDTO`、`XxxDO`、`XxxMapper`、`XxxServiceImpl` 等邻近命名 |
| 注入 | 普通 Spring 组件用 `@RequiredArgsConstructor` + `private final`；继承发送模板需要 `super(...)` 时写显式构造器 |
| 分层 | Controller 负责绑定参数、接口说明、调用 Service、包装响应；业务放 Service；持久化访问放 Mapper；不把 DO 当作对外接口模型 |
| 响应与异常 | oneCoupon 用 `Result<T>` / `Results.success(...)`；参数和业务前置条件不满足抛 `ClientException`，内部失败用 `ServiceException`，远程调用失败按现有 `RemoteException` 体系处理；由全局处理器转换 |
| 数据访问 | 基础操作复用 MyBatis-Plus；优先 Lambda Wrapper，参数化 SQL 用 `#{...}`；分页复用 `Page`/`IPage`，查询结果用 `convert` 转 RespDTO |
| 业务身份 | HTTP 路径从可信 `UserContext` 取当前店铺/用户，并校验上下文非空；MQ/定时/异步路径显式传递和校验身份，不能假定请求线程上下文存在 |
| 文档与日志 | 公共业务类/方法用中文说明职责，DTO 字段解释业务含义、枚举取值和必要的 `@Schema`；HTTP 接口沿用 `@Tag`/`@Operation`；用 `@Slf4j` 占位符日志记录关键 ID 与异常 |
| 格式 | 沿用邻近代码的四空格、同行左花括号和分段空行；实际格式化以已启用配置为准，勿把 200 字符配置解释为全项目强制行宽 |

## 4. 实现前检查关键语义

- 核对可信身份、租户/分片键和删除条件，不能只按请求 ID 更新跨店铺数据。
- 校验必填、数值范围、枚举成员、时间先后与字段依赖。`@Schema(required = true)` 是文档说明，不是运行时校验。责任链中只有注释的检查不算已实现。
- 多表原子业务在 Service 边界使用 `@Transactional(rollbackFor = Exception.class)` 或既有 `TransactionTemplate`，确认调用经过 Spring 代理。数据库事务不包含 Redis、MQ 或线程池。
- 库存与状态变更优先数据库条件更新并检查影响行数，避免“先查询再写回”。库存扣减 SQL 保留 `stock >= #{decrementStock}` 和身份/分片条件。
- 同步接口重复提交、MQ 重复投递、业务唯一性分别判断。`@NoDuplicateSubmit` 仅拦截同时持锁的请求，不能保证长期业务幂等；MQ 使用现有 `@NoMQDuplicateConsume` 时仍核对业务唯一键及提交边界。
- 外部消息或异步任务依赖数据库新记录时，安排在提交之后触发；需要可靠送达时再设计 outbox/事务消息等持久化方案。明确“提交后回调”自身无法保证宕机不丢消息。
- 缓存读写核对 key、数据类型、序列化、TTL 单位及失效策略。Redis Lua 只保证脚本在 Redis 内执行的原子性，不保证 Redis 与数据库一起回滚。
- 锁成功取得后用 `finally` 释放；线程池说明容量、拒绝策略、生命周期及失败恢复。不要把演示里的吞异常、硬编码身份或任务静默丢弃复制为默认规范。

## 5. 验证与交付

1. 查看 `git diff` 和构建配置，保留用户已有修改；先验证最小相关模块。Windows 从仓库根目录用 `mvn` 或存在且可用的 `mvnw.cmd`。
2. **oneCoupon 特别注意**：根 POM 把 Spotless `apply` 绑定到 `compile`，Eclipse formatter 块被注释，且本次快照缺少 `copyright/copyright.txt`。编译/测试前核对现场；需要避免格式化副作用时用项目插件支持的 `-Dspotless.apply.skip=true`。不要恢复用户删除的版权文件或执行全仓格式化来绕过错误。
3. 编译示例：`mvn -pl merchant-admin -am -Dspotless.apply.skip=true -DskipTests compile`。模块参数用实际 Maven 模块目录或 artifactId；构建其他模块时相应替换。
4. 测试先检查 Surefire/JUnit 配置与测试源码。现有 `*Tests` 有 HTTP 压测、数据生成、外部 Redis/DB 访问等，不能把全量 `mvn test` 当无副作用校验。确认 provider 确实发现并执行了测试，不以命令成功等同于测试通过。
5. 为实际改变的高风险业务验证越权、边界参数、重复请求、库存不足、并发、事务回滚或重投递中与本次相关的场景。只做文档/命名等低风险改动时不机械新增测试。
6. 交付说明改了什么、原因、验证命令和结果，以及尚未验证的外部依赖/一致性边界。审查时先列可定位的问题及影响；避免只点评样式。文档与代码输出都不要写入真实凭据或本地环境私有地址。

如果需要 UML 图，遵守仓库要求优先使用已安装的 `plantuml` skill；普通 Java 修改无需额外绘图。
