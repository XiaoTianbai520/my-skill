# oneCoupon 规范依据与差异

采样时间：2026-10-24。以下路径相对于 oneCoupon 仓库根目录，只用于定位来源；该 skill 被安装到其他目录后，不要相对于 skill 目录读取这些项目文件。目标仓库的新代码和有效配置优先于本快照。

## 配置事实

| 依据 | 可确认内容 |
| --- | --- |
| `pom.xml` | Java 17；Spring Boot 3.0.7；Spring Cloud 2022.0.3；MyBatis-Plus 3.5.7；Hutool、Fastjson2、Redisson、RocketMQ 等版本统一管理。这是项目版本快照，不是升级建议 |
| 根 POM 的 `modules` | framework、distribution、settlement、search、engine、merchant-admin、gateway；模块职责见原注释，是否实现要继续查源码 |
| `format/one-coupon_spotless_formatter.xml` | Eclipse 格式配置含 Java 17、四空格 tabulation 和 lineSplit=200；根 POM 的 Eclipse 配置块被注释，不能声称编译时强制套用 |
| 根 POM 的 Spotless execution | `apply` 绑定 `compile`；licenseHeader 引用 `copyright/copyright.txt`。本次工作区该文件为已删除状态，构建前重新检查。核对本地 2.22.1 插件 JAR 的 `META-INF/maven/plugin.xml`，可用参数为 `spotless.apply.skip` / `spotless.check.skip`，不是 `spotless.skip` |
| `lombok.config` | stopBubbling、Generated 标记、equals/hashCode 的 callSuper=skip；不要无故修改全仓配置 |
| 各模块 POM | 使用根 dependencyManagement；模块自行声明实际依赖，含各自 test 依赖；JUnit 发现与 Surefire 版本需要验证，不能仅看 test 依赖断言可执行 |

## 源码映射

| 主题 | 代表性文件 |
| --- | --- |
| 薄 Controller、统一响应、接口文档 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/controller/CouponTemplateController.java`；`engine/src/main/java/com/nageoffer/onecoupon/engine/controller/CouponTemplateController.java` |
| Service 接口/实现、租户条件、DTO 转换 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/service/CouponTemplateService.java`；同包 `impl/CouponTemplateServiceImpl.java` |
| DTO、分页、DO 与枚举 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/dto/req/CouponTemplateSaveReqDTO.java`、`CouponTemplatePageQueryReqDTO.java`；`dao/entity/CouponTemplateDO.java`；`common/enums/CouponTemplateStatusEnum.java` |
| 响应、异常、错误码 | `framework/src/main/java/com/nageoffer/onecoupon/framework/result/Result.java`；`web/Results.java`、`web/GlobalExceptionHandler.java`；`exception/`；`errorcode/` |
| 自动填充、分页 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/config/DataBaseConfiguration.java` |
| 责任链 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/service/basics/chain/MerchantAdminChainContext.java`、`MerchantAdminAbstractChainHandler.java`；`service/handler/filter/` |
| 请求身份与清理 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/common/context/UserContext.java`；`config/UserConfiguration.java` |
| 库存原子扣减 | `engine/src/main/resources/mapper/CourseTemplateMapper.xml`；`engine/src/main/java/com/nageoffer/onecoupon/engine/dao/mapper/CouponTemplateMapper.java` |
| 缓存回源、布隆、空值与锁 | `engine/src/main/java/com/nageoffer/onecoupon/engine/service/impl/CouponTemplateServiceImpl.java`；`framework/src/main/java/com/nageoffer/onecoupon/framework/config/RedisKeySerializer.java` |
| HTTP/MQ 防重实现 | `framework/src/main/java/com/nageoffer/onecoupon/framework/idempotent/NoDuplicateSubmitAspect.java`、`NoMQDuplicateConsumeAspect.java`；同目录注解和状态枚举 |
| 消息生产模板与环境后缀 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/mq/producer/AbstractCommonSendProduceTemplate.java`、`CouponTaskActualExecuteProducer.java`；同模块 `mq/base/MessageWrapper.java` |
| 消费事务与幂等 | `engine/src/main/java/com/nageoffer/onecoupon/engine/mq/consumer/UserCouponRedeemConsumer.java` |
| 异步统计与补偿 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/service/impl/CouponTaskServiceImpl.java`；`service/handler/excel/RowCountListener.java` |
| 批量分发与恢复 | `distribution/src/main/java/com/nageoffer/onecoupon/distribution/mq/consumer/CouponTaskExecuteConsumer.java`、`CouponExecuteDistributionConsumer.java` |
| 定时扫描 | `merchant-admin/src/main/java/com/nageoffer/onecoupon/merchant/admin/job/CouponTaskJobHandler.java` |
| 测试边界 | `merchant-admin/src/test/java/` 有集成测试、数据生成和并发 HTTP 请求；`distribution/src/test/java/` 有工具测试。先看方法实现，不能自动全量运行 |

## 需要保留的现实边界

1. `docs/coupon-template-and-task-create-flow.md` 曾描述 distribution 只有入口；本次工作区已有分发消费者。文档可作线索，实际行为以当前实现为准。
2. `UserConfiguration` 和 `NoDuplicateSubmitAspect#getCurrentUserId()` 使用固定模拟身份；这不是已完成的登录认证。新业务不继续扩散固定身份。
3. 参数校验里存在注释占位，部分日期检查被注释；不要把注释当执行中的规则。`@Schema` 也不会执行校验。
4. 部分类型为原始 `Page`、`Result`，部分 DTO `toString()` 用 JSON，存在 V1/V2 教学方法；不把这些全部提升成推荐标准。
5. DO `delFlag` 自动填充不等于存在 `@TableLogic`；元字段填充代码也需核对更新时的实际行为，不以方法名称推断一切正确。
6. 数据库事务内直接调线程池/Redis/MQ 的示例不提供跨资源原子性。消息消费者里使用请求 `UserContext` 的写法需要按事件身份改进。
7. 同一跨模块事件名不意味着消息字段完全相同；更改事件需核对生产者/消费者协议、环境后缀和序列化。
8. 本 skill 归纳开发方法，不复制项目业务实现、推广信息或版权声明；用户既有文件删除/修改保留，生成规范不应顺手修业务代码。
