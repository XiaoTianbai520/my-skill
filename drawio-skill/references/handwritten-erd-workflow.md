# 手写 XML 画 ER / 模块全景 / 数据库讲解图（Windows · drawio < v30 · 无 Graphviz dot）

本文件沉淀自一次真实任务：用 draw.io 讲解「高校选课平台」18 张表的数据库链路。
当时环境是 **Windows + drawio v29.7.9（< 30）+ 未装 Graphviz `dot`**，
导致所有依赖自动布局的脚本（`sqlerd.py` / `autolayout.py` / `compress.py`）都跑不了。
最终走「手写 XML + 固定坐标 + 两页结构」验证通过。把这套工作流记下来，下次直接复用。

## 0. 先用两条命令确认环境

```bash
drawio --version                  # 看主版本号；< 30 ⇒ 不支持 Mermaid 转换，也不能用 --layout
command -v dot || echo "no dot"  # 没装 dot ⇒ sqlerd / autolayout / compress 全部不可用
```

> 本机实测：`drawio`（无点号，由 `D:\software\draw.io\drawio.exe` 硬链接到 PATH）可用；
> `dot` 未安装；版本 29.7.9。因此**默认走手写 XML 路线**，不要去碰自动布局脚本。
> 每条机器结论（`--version` / `command -v dot`）都要先跑一遍复核，别凭记忆。

## 1. 推荐图结构：两页 .drawio

- **Page-1 模块全景**：把表按**业务语义**分成 4~6 个 `swimlane` 模块（不要按建表顺序 1..N）。
  模块之间用实线箭头标外键关系，主链路用虚线（如 `student → course_selection`）。
- **Page-2 核心链路**：选一张「枢纽表」（如 `course_selection`），放正中，
  向四周辐射它的外键目标表 + 周边资源表；每条边用 `value` 标出外键列名
  （如 `student_id` / `teaching_class_id` / `batch_id`）。

## 2. 起步模板（两页骨架，复制后替换文字即可）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="drawio" version="26.0.0">
  <diagram name="Page-1 模块全景">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="m1" value="① 账号与组织" style="swimlane;startSize=30;fillColor=#dae8fc;strokeColor=#6c8ebf;" vertex="1" parent="1">
          <mxGeometry x="40" y="40" width="320" height="220" as="geometry"/>
        </mxCell>
        <mxCell id="sys_user" value="sys_user" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="m1">
          <mxGeometry x="30" y="50" width="120" height="50" as="geometry"/>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
  <diagram name="Page-2 核心链路">
    <mxGraphModel>
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="hub" value="course_selection" style="shape=cylinder3;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;" vertex="1" parent="1">
          <mxGeometry x="360" y="280" width="160" height="90" as="geometry"/>
        </mxCell>
        <mxCell id="e1" value="student_id" style="edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;" edge="1" parent="1" source="student" target="hub">
          <mxGeometry relative="1" as="geometry" />
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

> 要点：多页靠多个 `<diagram>` 实现；`id="0"/"1"` 每页都要有；
> 容器子节点 `parent` 用容器 id，坐标相对容器；
> 边必须带 `<mxGeometry relative="1" as="geometry" />` 子元素，自闭合不渲染。
> 配色 / 间距 / 出入口点分布等通用规则见 `references/xml-authoring.md`。

## 3. 导出命令（本机验证可用）

```bash
# 预览（每页单独导出，不带 -e，宽度封顶避免超视觉上限）
drawio -x -f png --width 2000 -o docs/db-linkage_p1.png docs/db-linkage.drawio --page-index 1
drawio -x -f png --width 2000 -o docs/db-linkage_p2.png docs/db-linkage.drawio --page-index 2

# 终版（带 -e 内嵌 XML，双扩展名；-s 2 提高分辨率）
drawio -x -f png -e -s 2 -o docs/db-linkage_p1.drawio.png docs/db-linkage.drawio --page-index 1
drawio -x -f png -e -s 2 -o docs/db-linkage_p2.drawio.png docs/db-linkage.drawio --page-index 2

# 每次 -e PNG 导出后必跑：修复 drawio 截断的 IEND（issue #8）
python3 <this-skill-dir>/scripts/repair_png.py docs/db-linkage_p1.drawio.png
python3 <this-skill-dir>/scripts/repair_png.py docs/db-linkage_p2.drawio.png
```

- `--page-index` 在 ≤29 是 **1-based**（第二页 = `--page-index 2`）；旧文档写 0-based 是错的，以实测为准。
- 预览用 `--width 2000` 封顶；终版才用 `-s 2`，**不要**把 `--width` 与 `-s` 混用。
- < 30 不要用 `--layout`，也不要喂 `.mmd`（两者都会破坏参数解析 / 转换失败）。

## 4. 自检后必改的两类问题（本次实测踩到的）

1. **模块框太高 → 大片留白、版面失衡**：收紧各 `swimlane` 的 `height`，把箭头走廊重排到空出来的区域。
2. **边穿过无关图形**：在边里加 `<Array as="points"><mxPoint x=".." y=".."/></Array>` 绕行（例如改走右侧走廊），别让线压在形框边线上。

其余通用规则（配色、间距、出入口点分布）见 `references/xml-authoring.md`。
