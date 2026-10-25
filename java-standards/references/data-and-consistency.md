# 数据、缓存与消息一致性

## 数据库与隔离

- Mapper 复用 `BaseMapper<DO>`，复杂原子 SQL 放 `resources/mapper` 并使 namespace、方法和参数对应。仓库历史文件 `CourseTemplateMapper.xml` 实际对应 `CouponTemplateMapper`，不要把这个拼写差异当新命名规则，也不要顺手重命名破坏配置。
- 表名如 `t_coupon_template`，字段下划线、Java 属性驼峰；实体 `@TableName`，`createTime/updateTime/delFlag` 的 `@TableField(fill = ...)` 与 `MetaObjectHandler` 配套。自动填充删除标记不代表自动过滤逻辑删除。
- 涉及店铺数据的查询/更新带可信 `shopNumber`；用户券带正确 `userId`。分库分表还需核对 shardingsphere 配置，避免缺少路由键的全表扫描或错误更新。请求里的归属字段不能覆盖可信上下文。
- 缺少上下文要显式拒绝，不能用条件式 `.eq(shopNumber != null, ...)` 导致缺失身份时取消隔离。
- 库存扣减复用参数化条件更新，扣减量必须为正，影响行数为 0 时识别库存不足或状态变化。不要读出 stock 后在 Java 相减再覆盖。

```xml
<update id="decrementCouponTemplateStock">
    UPDATE t_coupon_template
    SET stock = stock - #{decrementStock}
    WHERE shop_number = #{shopNumber}
      AND id = #{couponTemplateId}
      AND stock >= #{decrementStock}
</update>
```

- 状态迁移在 UPDATE 中带原状态，防止重投递或并发覆盖新状态。业务唯一性由合适的唯一索引或条件更新承接；消息标识与业务唯一键需要分别定义。

## 本地事务

- 多次数据库操作要求共同成功时沿用 `@Transactional(rollbackFor = Exception.class)`；已有代码也使用 `TransactionTemplate`。确认 Spring 代理生效、异常没有被吞、异常传播触发回滚。
- Redis、RocketMQ、线程池不参与这一本地事务。明确每个外部副作用的时机与失败恢复，不写“加事务就保证最终一致”。
- 需要新写入记录的 MQ/线程池任务应在提交成功后触发；以提交后回调减少早消费，但进程在提交后、回调发送前崩溃仍可能丢失。
- 业务要求可靠送达时选择与项目契合的持久化 outbox、事务消息或可重扫任务；这是需要设计和验证的改进，不要声称仓库已经提供。
- 批处理尤其注意外部消息、Redis 更新与数据库批次提交先后，确认失败如何重试和补偿，避免只给一层事务注解。

## Redis 与并发

- 复用模块的 `*RedisConstant`，核对 `StringRedisTemplate` 与 Redisson 的 key 前缀配置。`RedisKeySerializer` 会添加全局前缀，检查最终 key 后再决定业务常量，避免重复前缀。
- 模板常见 Hash；用户券列表存在 ZSet；布隆过滤器只作存在性预判。缓存数据结构与生产者/消费者/定时失效路径保持兼容。
- 高并发缓存回源可沿用“缓存 → 布隆过滤器/空值缓存 → 分布式锁 → 锁内再次检查 → DB → 重建缓存”。仅在确有并发和穿透风险时使用，不给每个后管查询加缓存。
- Redis Lua 可合并 Hash 写入与过期时间设置，或做原子库存/限领校验；核对 `KEYS`/`ARGV`、返回码和空值，不拆成多个非原子命令。
- `EXPIREAT` 是秒级时间戳；消息任意延时接口和 Java `Date#getTime()` 用毫秒，`keyTimeout` 等按其声明换算，不混用。
- 读取缓存也要检查业务有效性和归属；仅命中 key 不能等同于已验证权限或有效期。
- 锁仅在成功获取后进入释放路径，用 `try/finally`。分布式锁不能替代数据库库存条件/唯一约束；长任务核对锁持有期限和续租。

## RocketMQ 与幂等

- 按模块组织 `mq.event`、`mq.base`、`mq.producer`、`mq.consumer`，消息体用业务 `XxxEvent`，封装沿用 `MessageWrapper<T>`。
- 生产者继承现有 `AbstractCommonSendProduceTemplate<T>`，实现发送参数和消息构建；显式构造器把 `RocketMQTemplate` 传给基类。复用 `BaseSendExtendDTO` 定义事件名、topic、keys、超时/延迟。
- Topic/consumerGroup 遵循相邻命名并保留环境占位符 `${unique-name:}`；生产者用 `environment.resolvePlaceholders(...)` 等现有方式解析。业务 key 用任务 ID/业务 ID，header 与包装器保持一致。
- 消费者实现 `RocketMQListener<MessageWrapper<Event>>`，从事件读取业务身份与参数；请求线程的 `UserContext` 不保证在消息线程存在。
- 使用 `@NoMQDuplicateConsume(keyPrefix = ..., key = ..., keyTimeout = ...)` 前核对实际方法签名和 SpEL。组件通过 Redis 区分 CONSUMING/CONSUMED，异常时删除 key 后重新抛出，TTL 使用秒。它不等于永久去重，也不保证数据库提交和去重标记共同成功。
- `@NoDuplicateSubmit` 用请求路径、用户和参数摘要构造锁，成功后 finally 解锁；当前实现用户为模拟值，只限制同时执行，释放锁后同样请求可再次进入。不要用它代替领券唯一约束或业务幂等号。
- 异常应该保留可重试信号。仅在明确识别到“业务效果已完成”时对重复消息直接返回；不要捕获所有异常后记录一句就成功确认。

## 异步、Excel 与定时任务

- Excel 大文件沿用 EasyExcel 监听器流式处理，避免一次性加载；保留批次、行号、失败记录等重试定位信息。
- 明确线程池容量、队列、拒绝策略、关闭和上下文传递。当前行数统计的 `DiscardPolicy` 依赖延迟队列补偿，不代表任何异步工作都可以静默丢弃。
- `TransmittableThreadLocal` 出现在仓库中不等于线程池一定正确传递；需要时验证包装器/提交方式，并在执行完毕清理。MQ 和定时任务优先携带显式业务字段。
- XXL-Job 复用现有 `@XxlJob` 组织；扫描采用游标/有界批次，条件状态更新后再触发任务，失败保留可恢复状态。调度执行成功不等于发券业务完成。

## 相关验证场景

按实际改动选取：空身份、跨店铺 ID、负数扣减、库存恰好不足/足够、并发扣减、重复消息、处理失败后重投、事务回滚、提交前被消费、提交后发送失败、缓存过期、锁释放、时间单位，以及线程池拒绝后的恢复。只声称已实际执行的验证。
