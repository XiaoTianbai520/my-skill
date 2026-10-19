---
name: openapi-example-inject
description: 为 Spring Boot + Knife4j/springdoc-openapi 项目批量注入接口调试默认值（@Schema(example) 到请求 DTO 字段、@Parameter(example) 到 Controller 路径/查询参数），让 Knife4j 文档页每个接口预填示例值，点发送即可联调。当项目已集成 Knife4j/OpenAPI、需要给全部接口配置可直接看到结果的默认值时使用。
agent_created: true
---

# OpenAPI 接口调试默认值注入

## 适用场景
- 项目已引入 `springdoc-openapi` 或 `knife4j-openapi3-jakarta-spring-boot-starter`（Spring Boot 3 / Jakarta）。
- 用户希望 Knife4j 文档页（`/doc.html`）每个接口都能「直接看到结果」——即请求体与路径/查询参数预先填好示例值，免手动填参即可点「发送」联调。

## 原理
OpenAPI 的 `example` 值会被 Knife4j 调试面板预填：
- 请求体（DTO）字段：用 `io.swagger.v3.oas.annotations.media.Schema` 的 `example` 属性。
- 路径变量 / 查询参数（`@PathVariable` / `@RequestParam`）：用 `io.swagger.v3.oas.annotations.Parameter` 的 `example` 属性。
- `@RequestBody` DTO 的示例值由 DTO 字段上的 `@Schema(example)` 提供，无需在 Controller 再标注。

## 实现步骤（数据驱动脚本，推荐用 Python）
1. **提取字段**：扫描 `**/dto/req/*.java`，正则 `^\s*private\s+([\w<>,\s]+?)\s+(\w+)\s*;` 拿到字段名+类型；扫描 Controller 拿 `@PathVariable`/`@RequestParam` 参数名。
2. **建字典**：字段名 → 示例值（见下方 `EXAMPLES`），`status` 字段按 DTO 文件名给合法枚举/状态码值（`STATUS_EXAMPLES`）。
3. **注入 DTO**（`@Schema(example)`）：
   - 先去掉文件里已有的 `@Schema(example = ...)` 行与 `import io.swagger.v3.oas.annotations.media.Schema;` 行，保证幂等。
   - 重建文件：**逐行**读，遇到 `private` 字段行时，从「新行列表末尾连续的 `@` 注解行」前面插入 `@Schema(example = "值")`；否则原样追加。
   - 若注入了注解，在 `package` 行后补 `Schema` import。
   - 缩进取对应注解行的缩进。
4. **注入 Controller**（`@Parameter(example)`）：对每行含 `@PathVariable`（非 `@Parameter` 已存在、非 `MultipartFile`）的前面插入 `@Parameter(example = "1") `；`@RequestParam` 同理，`title` 给 `"测试导出"`，其余 ID 给 `"1"`。import 缺失则补 `io.swagger.v3.oas.annotations.Parameter`。该步是按行字符串替换，天然幂等（已含 `@Parameter(` 则跳过）。
5. **编译验证**：`mvn -B -q compile`（需联网时挂代理 `-Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890`）。

## 关键坑
- **不要逐字段在原数组上 `insert`**：同一文件多字段时，先前的 insert 会改变后续索引，导致后面的注解被插进 javadoc 注释里（注释里的注解是纯文本，不生效）。必须「先剥离旧注解再重建」，或直接对新行列表从末尾连续 `@` 块重排插入。
- `@Schema` 在同一元素上不可重复（非 `@Repeatable`），重复会编译报错——务必先剥离再注入。
- 枚举字段的 example 必须是该枚举的合法存储值（如 `RoleEnum` 的 `STUDENT`、`CourseTypeEnum` 的 `REQUIRED`），否则 Knife4j 发请求会触发校验失败。注入前先读实体/枚举确认取值。

## 示例值字典（按需扩展）
```python
EXAMPLES = {
    "academicYear": "2026-2027","batchId": "1","batchName": "2026秋季选课批次","buildingName": "教学楼A",
    "capacity": "50","classCode": "CS2601","classId": "1","className": "计算机2601班","classroomId": "1",
    "courseCode": "MATH101","courseId": "1","courseName": "高等数学","courseType": "REQUIRED","credit": "3",
    "defaultCapacity": "50","description": "这是一段测试描述","dropDeadline": "2026-09-30 23:59:59",
    "endDate": "2026-12-31","endSection": "2","endTime": "2026-09-01 10:00:00","endWeek": "16","entryYear": "2026",
    "excludeScheduleId": "1","gradeId": "1","gradeIds": "[1, 2]","gradeName": "2026级","id": "1","isRead": "0",
    "keyword": "测试","loginType": "STUDENT","majorCode": "CS001","majorId": "1","majorIds": "[1, 2]",
    "majorName": "计算机科学与技术","maxSelectionCredit": "25","noticeType": "SELECTION_START",
    "page": "1","pageSize": "10","password": "123456","roomNo": "A101","score": "85",
    "semesterCode": "2026-2027-1","semesterId": "1","startDate": "2026-09-01","startSection": "1",
    "startTime": "2026-09-01 08:00:00","startWeek": "1","studentId": "20260001","studentName": "李娜",
    "studentNo": "20260001","teacherId": "T10001","teacherName": "张伟","teacherNo": "T10001",
    "teachingClassId": "1","teachingClassIds": "[1, 2]","termNo": "1","title": "系统通知标题",
    "username": "20260001","weekday": "1",
}
# status 按 DTO 文件名给合法枚举/状态码（如 EnableStatusEnum 用整型码 "1"；各业务状态枚举用其存储字符串）
STATUS_EXAMPLES = {
    "StatusUpdateReqDTO": "1","StudentPageQueryReqDTO": "1","TeacherPageQueryReqDTO": "1",
    "MajorPageQueryReqDTO": "1","CoursePageQueryReqDTO": "1","AcademicClassPageQueryReqDTO": "1",
    "ClassroomPageQueryReqDTO": "1","GradePageQueryReqDTO": "1","StudentSelectionQueryReqDTO": "SELECTED",
    "SemesterPageQueryReqDTO": "ACTIVE","SelectionBatchPageQueryReqDTO": "IN_PROGRESS",
    "TeachingClassPageQueryReqDTO": "AVAILABLE","SelectionBatchStatusUpdateReqDTO": "IN_PROGRESS",
    "TeachingClassStatusUpdateReqDTO": "AVAILABLE","SemesterStatusUpdateReqDTO": "ACTIVE",
}
```
注：本技能在某教务选课平台项目落地，覆盖 36 个请求 DTO（130 处 `@Schema`）+ 23 个 Controller（58 处 `@Parameter`），编译通过。
