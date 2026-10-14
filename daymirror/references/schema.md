# 数据与命令接口 v1

## 工作空间

```text
<workspace>/
  config.json        schema_version、IANA timezone、创建时间
  sessions/         <session_id>.json
  journals/         <date>--<session_id>--v<version>.md
  inputs/           AI 客户端准备的私密 JSON 输入
  .daymirror.lock   短时系统锁；进程退出自动释放，不删除锁文件
```

会话编号为 32 位小写十六进制字符串。日期为真实存在的 YYYY-MM-DD，时区采用 IANA 名称。时间戳使用含时区的 UTC ISO 格式。

会话包含 schema_version、session_id、date、timezone、created_at、updated_at、status、revision、content_revision、current_question、synthetic、questions、journal_payload、exports。

- status 为 active、paused、completed。20 个问题均 answered/skipped 后，仍需 AI 生成总结并调用 save，才变为 completed。
- questions 是有序 20 项，每项为 id、number、round、text、status、answer。新会话两轮所有 text 初始均为 null，AI 逐题生成并通过 question 保存；只有当前题可生成。旧会话已保存的基础题仍按原文保留。
- current_question 为当前待回答题号，全部完成时为 null。
- revision 是会话写入版本；content_revision 只在问题或回答变化时增加，防止旧总结覆盖新回答。
- journal_payload 是最近保存的总结输入；修改答案后可变为过期，必须重新生成。exports 保留版本、相对文件名、完整性哈希和完成状态。

工具拒绝不支持的 schema_version、损坏会话和非法输入，不自动重置数据。

## 命令

运行 `python -X utf8 <skill-root>/scripts/daymirror.py <command> ...`。每个命令接受 `--workspace <absolute-path>`。本仓库默认路径为其根目录下的 private/workspace；已安装到其他位置时应显式指定数据目录。

| 命令 | 额外参数 / 输入 | 行为 |
|---|---|---|
| init | --timezone Asia/Shanghai | 初始化；相同时区重复调用不会清空数据 |
| start | 可选 --date YYYY-MM-DD；--synthetic 仅供示例 | 新会话，20 个文本为空的进度槽位；不指定日期时按工作空间时区计算 |
| status | 可选 --session ID | 返回完整会话与当前进度 |
| list | 无 | 列出会话摘要，不导出所有原始回答 |
| question | --input FILE，内容为 {"question_id":"q01","text":"..."} | 两轮均可保存当前问题，文本包括当题需要的选项；重复相同题号与文本幂等 |
| answer | --input FILE，内容为 {"question_id":"q01","answer":"用户原话"} | 回答当前题目，重复相同题号与回答幂等 |
| skip | --question q01 | 跳过指定当前题目，重复请求幂等 |
| edit | --number N --input FILE，内容为 {"answer":"修正后的原话"} | 修正已回答或跳过的题目，保留其他题目 |
| pause | 无输入 | 保存暂停状态，不自动生成日记 |
| resume | 无输入 | 恢复活动状态，返回完整问答和当前问题 |
| save | --input FILE，总结结构见下；可省略输入重复保存 | 保存完整/部分日记；修正后新版本，重复内容幂等 |
| demo | 可选 --workspace 空目录 | 使用内置合成问答启动独立进程回放，默认写入项目 work/demo 下的新目录 |

除 init、start、list、demo 外，命令接受 --session ID。未指定时优先最近未完成会话；不存在未完成会话时选择最近完整会话。AI 在 start/resume 后应固定使用返回的编号。

--input - 表示从标准输入读取 JSON。Windows 使用 UTF-8 文件或 Python 的 UTF-8 标准输入，避免在命令参数里暴露回答。

question_id 必须为 q01–q20。新回答或跳过必须对应当前题目；重复同一请求不会误记录到下一题。已回答题目需要改变原话时使用 edit，不能用 answer 覆盖。

成功退出码 0，stdout 为 {"ok":true,"result":...}；业务或文件错误退出码 2，stderr 为 {"ok":false,"error":{"code":"...","message":"..."}}。--help 和 --version 是供人阅读的输出。

当前题目为 null 且 ready_to_save 为 true 时，客户端应自动总结并调用 save。Python 本身不能调用 AI 生成总结。

## save 输入

以 `assets/journal_input_template.json` 为完整空模板，字段必须齐全：

- content_revision：最新 status 返回的内容版本。
- summary：overview 是下述条目或 null；events、reflections、learnings、obstacles、actions 为条目数组。
- metrics：下面八个字段，每个可为 null。
- metric_sources：与 metrics 对应的八个问题编号数组。
- tags：不重复的非空字符串数组，可为空。

总结条目形状为 {"text":"内容","kind":"reported_fact","source_questions":["q01"]}。

事件、反思、收获、阻碍和概览的 kind 为 reported_fact、self_assessment、hypothesis。actions 的 kind 为 suggestion 或 user_commitment。每条至少引用一个已回答的问题，跳过或未回答的问题不可作为证据。

| 指标 | 单位 / 校验 | 定义 |
|---|---|---|
| sleep_hours | 数值，0–24 | 用户所述本次睡眠小时数，不推导睡眠质量 |
| focus_minutes | 数值，0–1440 | 用户明确报告的深度专注分钟数 |
| planned_tasks | 非负整数 | 当天计划任务数 |
| completed_tasks | 非负整数，已知计划数时不能超过它 | 计划内完成任务数，额外任务写入正文 |
| mood | 整数，1–10 | 越高越积极，仅用户自评 |
| energy | 整数，1–10 | 越高越充沛，仅用户自评 |
| stress | 整数，1–10 | 越高压力越大，仅用户自评 |
| exercise_minutes | 数值，0–1440 | 用户报告的运动分钟数 |

每个非空指标至少引用一个已回答的问题；null 指标来源为空数组。布尔值、NaN、无穷值、评分越界和负时长会被拒绝。分钟数可为小数，确定的单位换算允许保留精度。

脚本验证引用存在性，不能验证原话与数值的语义一致性。AI 必须核对用户是否真的提供了数字、其计量口径是否一致，不以填满指标为目标。

## Markdown

YAML frontmatter 包含 schema_version: 1、date、timezone、session_id、journal_version、content_revision、interview_complete、answered_questions、skipped_questions、pending_questions、synthetic、八个数值字段、metric_sources 和 tags。

正文固定为今日概览、关键事件、深度反思、今日收获、存在的问题、明日行动、原始问答。原话用可容纳反引号的代码块保存，不让用户输入破坏章节结构。

脚本读取 frontmatter 时使用 yaml.safe_load；不要使用可执行对象的 YAML 加载器。日记版本不可静默覆盖。会话 JSON 原子替换；新 Markdown 用完成写入后的文件发布。若 Markdown 成功而会话写入失败，同样输入重试会复用该文件。

日记遭到手工修改后，重复保存会返回 export_changed 而不覆盖修改。需要修正时用 edit / 新总结导出新版本，保留手工修改文件。
