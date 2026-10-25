# 分层与编码

## 包与模块

oneCoupon 根包为 `com.nageoffer.onecoupon`，业务模块包为 `merchant.admin`、`engine`、`distribution` 等。`framework` 提供响应、异常、错误码、Web 自动配置、缓存配置和幂等组件。共性组件放 framework，业务 DTO、DO 和规则留在所属业务模块；不要把别的服务的实现类直接作为依赖。

仓库的 search/settlement 当前主要是入口与配置，不能从模块名称推断业务已实现。创建模块功能前先看实际源码。

## HTTP 与 DTO

- oneCoupon 路由惯例是 `/api/merchant-admin/coupon-template/create|page|find|increase-number`、`/api/engine/...` 等业务前缀加动作；遵循目标模块邻近路由，不在小改动中全量改 REST 风格。
- JSON 请求用 `@RequestBody`；查询条件遵循现有 GET 绑定。创建动作返回 `Result<Void>`，查询返回 `Result<RespDTO>`，分页返回 `Result<IPage<RespDTO>>`。
- 新接口在 Controller 上保留 `@RestController`、`@Tag`，方法用 `@Operation` 描述业务。依赖用 `private final` 配合 `@RequiredArgsConstructor`。
- 输入参数通常名为 `requestParam`，事件为 `event`/`messageSendEvent`，转换后的输出可叫 `actualRespDTO`。以可读性为准，不机械改历史变量。
- 请求对象用 `@Data`；API 模型加 `@Schema`，字段写中文业务说明。持久层实体用 DO 后缀及 `@TableName`，按需要采用 `@Builder`、全参/无参构造。不要为无用的构造方法加注解。
- `Long` 数据库 ID 与字符串接口 ID 在仓库中并存；保持原合同并明确转换边界。日期 DTO 已有 `@JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss", timezone = "GMT+8")`，不要只改一层导致协议变化。
- 分页请求邻近实现继承原始 `Page`。新代码可在确认版本与 Mapper 泛型兼容后补全泛型；不要据此要求所有历史类重写，也不要凭空切换为 Spring Data `Pageable`。

## Service 与转换

- 业务接口位于 `service`，实现位于 `service.impl`；已有接口通常继承 `IService<DO>`，实现继承 `ServiceImpl<Mapper, DO>`。需要通用 CRUD 时沿用，不强制所有无持久化服务继承这些类型。
- 在 Service 做身份、参数语义、状态判断、业务编排、事务和 DTO/DO 转换；Controller 不访问 Mapper/Redis。
- 复用 Hutool `BeanUtil.toBean` / `copyProperties`；分页 `IPage<DO>.convert(...)` 转为 RespDTO。复制后显式覆盖身份、初始状态、批次号等受服务端控制的字段，防止请求字段越权赋值。
- 业务枚举使用明确的 `code/status/type` 和说明，按实际枚举访问器取值，不假定统一叫 `getCode()`。
- 单类简单校验不必新建模式。已有模板创建责任链按照 `mark()` 归组，`getOrder()` 升序执行，非空、基本规则、依赖核验当前顺序为 0、10、20。新增同类检查可插入链中，但不要在多个层重复同一规则。
- 参数校验失败走 `ClientException`；操作未达到预期等内部失败走 `ServiceException`。HTTP 响应交给 `GlobalExceptionHandler`，不要每个 Controller 捕获 `Exception` 后返回成功或自造错误 Map。
- 新代码保留泛型，避免原始 `Result`、`Map` 和无必要强转；历史原始类型是兼容背景，不是推荐写法。

## 可维护性与日志

- 依赖管理由根 `dependencyManagement` 统一；模块声明实际需要的依赖。使用现有 Hutool、Fastjson2、MyBatis-Plus 等前先核对模块 POM，不为一处转换新增整套库。
- 用中文 Javadoc 说明类/方法业务职责，公开方法必要时写 `@param`/`@return`；复杂步骤解释约束或补偿原因，不照抄宣传内容和原作者信息。
- 通过 SLF4J `{}` 记录任务 ID、模板 ID、消息 key、操作结果；异常作为最后一个参数保留堆栈。日志含请求/消息内容时先判断敏感字段与体积，不把全对象序列化当硬性要求。
- `@SneakyThrows` 和捕获 `Throwable` 在样本中存在，但不因此成为所有方法的默认；按异常语义显式传播，避免吞掉失败而破坏事务和重试。
- 不把 `System.out`、硬编码用户、全局静态可变业务状态加入生产代码。

## 最小示例（示意，需按真实 DTO 字段补全）

```java
@RestController
@RequiredArgsConstructor
@Tag(name = "优惠券模板管理")
public class CouponTemplateController {

    private final CouponTemplateService couponTemplateService;

    @Operation(summary = "分页查询优惠券模板")
    @GetMapping("/api/merchant-admin/coupon-template/page")
    public Result<IPage<CouponTemplatePageQueryRespDTO>> pageQueryCouponTemplate(
            CouponTemplatePageQueryReqDTO requestParam) {
        return Results.success(couponTemplateService.pageQueryCouponTemplate(requestParam));
    }
}
```

Service 中约束店铺并转出 DTO：

```java
Long shopNumber = UserContext.getShopNumber();
if (shopNumber == null) {
    throw new ClientException("当前店铺信息缺失");
}
LambdaQueryWrapper<CouponTemplateDO> queryWrapper = Wrappers.lambdaQuery(CouponTemplateDO.class)
        .eq(CouponTemplateDO::getShopNumber, shopNumber)
        .like(StrUtil.isNotBlank(requestParam.getName()),
                CouponTemplateDO::getName, requestParam.getName());
IPage<CouponTemplateDO> selectPage = couponTemplateMapper.selectPage(requestParam, queryWrapper);
return selectPage.convert(each -> BeanUtil.toBean(each, CouponTemplatePageQueryRespDTO.class));
```

示例不声明逻辑删除自动生效。项目 DO 的 `delFlag` 自动填充并不等于配置了 `@TableLogic`；需要过滤删除数据时先检查实际配置或显式加条件。
