# java-standards

从 oneCoupon 的构建配置、Java 实现和跨模块调用方式提炼的中文 Java 开发 skill。适用于按项目风格新增接口、修改业务、重构和代码审查。

## 内容

- `SKILL.md`：触发说明、工作步骤、核心约定、验证流程。
- `references/layers-and-style.md`：包结构、命名、DTO/DO、分层、注解、日志与示例。
- `references/data-and-consistency.md`：数据库、租户/分片条件、库存、Redis、MQ、幂等、事务、线程池及任务。
- `references/onecoupon-evidence.md`：规范来源、配置事实、历史代码与文档差异。
- `evals/evals.json`：分页查询、库存扣减、事务消息审查三个回归场景。

## 使用

在支持 skill 的客户端中，将整个 `java-standards` 目录放入该客户端的技能目录，并在新会话中确认它已被发现。也可在当前任务中直接指定 `SKILL.md` 路径，让执行者先读取它。

示例：

```text
$java-standards 按项目规范，为 merchant-admin 的优惠券模板分页增加状态筛选。
$java-standards 审查这个消费者的事务、重试和用户身份传递。
```

迁移到其他仓库时，先读取目标仓库约定，再决定适用规则；oneCoupon 的包名、版本、优惠券业务和环境配置不是所有 Java 项目的默认值。

评测结果保存在源仓库的 `skills/java-standards-workspace/`，不需要随 skill 安装。评测输出是隔离的实现建议与代码片段，不代表对业务源码的修改或已经通过编译的补丁。
