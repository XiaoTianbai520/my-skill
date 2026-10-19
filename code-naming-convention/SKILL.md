---
name: code-naming-convention
description: 项目后端 Java 代码命名与开发规约（方法/参数/领域模型/代码风格/注释/消息队列）。当编写、审查或重构 Java 代码、Controller/Service/Mapper 分层代码、DTO/DO 等领域对象，或涉及 RocketMQ Topic/Tag/生产者组/消费者组命名时，应使用本技能确保命名符合团队规范。
agent_created: true
---

# 代码命名与开发规范

## Overview

本技能规定团队 Java 后端项目的统一命名与编码约定，覆盖方法命名、参数命名、领域模型命名、代码开发规约、注释规范与消息队列规约。当编写新代码、审查他人代码、重构存量代码，或生成 DTO/DO/Mapper/Service 等分层代码时，严格遵循以下规则，保持代码风格一致、见名知意。

触发场景包括但不限于：
- 编写或审查 Controller、Service、Mapper 三层代码
- 定义 DO / DTO（ReqDTO / RespDTO）/ Configuration / Constant / Context / Enum 等对象
- 命名方法、变量、静态常量、异常变量、循环变量
- 编写方法级与类级注释
- 设计或审查 RocketMQ 的 Topic、Tag、生产者组、消费者组及相关收发代码

---

## 一、方法命名

方法命名使用统一前缀，做到见名知意。

1. **获取单个对象**用 `get` 作前缀。
   - 示例：查询单个用户 `getStudent`；按 ID 查询单个用户 `getStudentById`。
2. **获取多个对象**用 `list` 作前缀。
   - 示例：按 IDS 查询多个用户 `listStudentByIds`。
3. **获取统计值**用 `count` 作前缀。
   - 示例：统计全量用户 `countUser`。
4. **插入**用 `save` 作前缀。
   - 示例：新增用户 `saveUser`。
5. **删除**用 `remove` 作前缀。
   - 示例：删除用户 `removeUser`。
6. **修改**用 `update` 作前缀。
   - 示例：修改用户 `updateUser`。

> 除上述六类外，查询语义也可用 `find` 等（如 `findCouponTemplate`），但凡涉及「增删改查单/多/统计」优先使用上述统一前缀。

---

## 二、参数命名

### 1. 对象参数命名

针对 Controller、Service、Mapper 三层架构中的**单个对象请求参数**，统一使用 `requestParam` 命名。

```java
/**
 * 查询优惠券模板
 *
 * @param requestParam 请求参数
 * @return 优惠券模板信息
 */
CouponTemplateQueryRespDTO findCouponTemplate(CouponTemplateQueryReqDTO requestParam);
```

### 2. 单参数命名

基础类型和引用类型语义单一，直接使用其本身的语义单词命名。

```java
/**
 * 查询优惠券推送任务详情
 *
 * @param taskId 推送任务 ID
 * @return 优惠券推送任务详情
 */
CouponTaskQueryRespDTO findCouponTaskById(String taskId);
```

---

## 三、领域模型命名规约

| 类型 | 后缀 | 说明与示例 |
|------|------|-----------|
| 数据对象 | `xxxDO` | xxx 为数据表名，如 `StudentDO` |
| 数据传输对象 | `xxxDTO` | xxx 为业务领域名，分入参/出参 |
| 项目配置类 | `xxxConfiguration` | 如 `DataBaseConfiguration` |
| 常量类 | `xxxConstant` | 如 `RedisCommonConstant` |
| 上下文 | `xxxContext` | 如 `UserContext` |
| 枚举类 | `xxxEnum` | 如 `UserCouponStatusEnum` |

### DTO 入参 / 出参细分

以学生新增接口为例：
- 入参：`StudentSaveReqDTO`
- 出参：`StudentSaveRespDTO`

以学生分页查询接口为例：
- 入参：`StudentPageQueryReqDTO`
- 出参：`StudentPageQueryRespDTO`

### 注意事项

- POJO 是 DO / DTO / BO / VO 的统称，**禁止**命名成 `xxxPOJO`。

---

## 四、代码开发规约

【强制】类、方法和变量的命名要做到**顾名思义，避免使用缩写**。

【强制】静态变量使用**大写**，多个单词使用**下划线**连接。
- 示例：`MESSAGE_CENTER_SEND_TYPR`（注：原始规范示例拼写如此，实际项目请自检拼写）。

【强制】捕获的异常名称命名为 `ex`；捕获异常且**不做任何事情**时，异常名称命名为 `ignored`。

【强制】返回值变量使用 `result` 命名；循环中使用 `each` 命名循环变量；map 中使用 `entry` 代替 `each`。

```java
// result 命名示范
private Result parseDate(String data) {
    Result result = JSONUtil.parseObject(data, Result.class);
    return result;
}
// 或采用 result 为前缀
private Result parseDate(String data) {
    Result resultDate = JSONUtil.parseObject(data, Result.class);
    return resultDate;
}

// each 命名示范
appNameLeaseMap.values().forEach(each -> appNameLeaseList.add(each));
// 或是 for 循环
for (Lease<InstanceInfo> each : appNameLeaseMap.values()) {
    appNameLeaseList.add(each);
}
```

【强制】业务系统中**优先使用 Guava、HuTool、Common3** 等工具类中的方法，不存在指定方法时再创建自定义工具类，**禁止**创建相同语义方法的工具类。
- 备注：定义**组件项目**时，尽量使用自定义工具类，避免因版本问题导致不确定的异常。

---

## 五、注释规范

### 1. 类注释说明意图即可

【强制】Class、Interface、Enum、`@interface` 等文件类型，类上注释**仅需说明类的意图**即可，**不需要**补充时间和创建人（开发不止一人，易成信息干扰；需要的话查看提交记录）。

```java
/**
 * 适配第三方框架的线程池
 */
public interface ThreadPoolAdapter {

}
```

### 2. 方法上需要添加注释

【强制】方法上需添加注释，说明清楚方法的意图（接口实现类无需注释）；必要时描述 `@param` `@return`。

```java
/**
 * 适配第三方框架的线程池
 */
public interface ThreadPoolAdapter {

    /**
     * 修改框架线程池的核心参数
     *
     * @param threadPoolBaseInfo  修改线程池的基础参数
     * @return  线程池核心参数修改结果
     */
    boolean updateThreadPool(ThreadPoolBaseInfo threadPoolBaseInfo);
}
```

- 若方法为内部引用方法，且方法名称**见名知意**，无需方法注释。

### 3. 方法块内部注释规范

【强制】方法内部的注释，**应新起一行**，而不是跟在代码后面。

```java
// 正例
// 刷新动态线程池参数
refreshDynamicPool(parameter, executor);

// 反例
refreshDynamicPool(parameter, executor); // 刷新动态线程池参数
```

### 4. 私有方法通过命名说明意图

【强制】私有方法尽量通过方法命名说明方法语义，减少对注释的依赖。

---

## 六、消息队列规约（RocketMQ）

### 1. 命名规范

RocketMQ 相关命名**强制使用英文小写**。

1. 【强制】**Topic 命名**：`业务线_项目名_topic`。业务线或项目含多个单词，使用 `-` 分割。
   - 示例：`common_message-center_topic`
2. 【强制】**Tag 命名**：`业务线_项目_业务_tag`。
   - 示例：`common_message-center_send-message_tag`
3. 【强制】**生产者组命名**：`业务线_项目_业务_pg`。
   - 示例：`common_message-center_send-message_pg`
4. 【强制】**消费者组命名**：`业务线_项目_业务_cg`。
   - 示例：`common_message-center_send-message_cg`

### 2. 使用规范

#### 2.1 消息发送

1. 【强制】消息生产者创建时，**必须指定生产者组**。
2. 【强制】一个系统对应**一个 Topic**，系统下的不同业务根据 **Tag** 区分。
3. 【强制】发送消息时，需设置 **KEYS**（建议定义为业务唯一标识，如订单 ID）。
4. 【强制】发送消息无论成功或失败，需打印 **KEYS、Payload、执行时间以及 SendResult**。
5. 【强制】发送消息时需设置**超时时间**，建议设置在 **2000ms 内**，避免应用被拖垮。
6. 【建议】可靠性较高的消息，发送失败后可存储到 DB，开启定时任务扫描并重新投递。

#### 2.2 消息消费

1. 【强制】消费端创建时，**必须指定消费者组**。
2. 【强制】消费端需要**保证数据幂等**。
3. 【强制】消费消息无论成功或失败，需打印 **KEYS、MsgId、执行时间以及 Message**。
4. 【强制】不同的应用集群应使用不同的消费者组；若不同应用集群需订阅同一消费者组，需保证 Topic Tag 订阅关系一致。
5. 【强制】打印消息消费日志：
   ```java
   log.info("Execute result: {}, Keys: {}, Dispatch time: {} ms, Execute time: {} ms, Message: {}", ...);
   ```
6. 【建议】消费时尽量**不设置重试**（多数失败重试后仍会失败，反而影响消费进度）；特定场景应在代码中自行设置重试逻辑。
7. 【建议】消费者并发消费数量默认 1（串行化），应基于系统场景设置并发数，并考虑消费过程中其它组件压力：
   - 系统 CPU 任务少：`CPU 核数 / (1 - 阻塞系数 0.8)`
   - 系统 CPU 任务较多：建议 `CPU 核数 + 1`

---

## 用法提示

- 生成 / 审查代码时，逐项比对上述规则，特别是方法前缀、DTO 命名、静态常量大写、异常与循环变量命名。
- 涉及 RocketMQ 时，先确定 `业务线` 与 `项目名`，再按 `Topic/Tag/生产者组/消费者组` 规则拼接，并补齐全量【强制】项（生产者组、KEYS、超时、日志、幂等）。
