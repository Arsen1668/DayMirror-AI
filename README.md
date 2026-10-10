# DayMirror v0.1

让 AI 逐题采访你，把一天的经历保存为有统一数据结构、可以暂停恢复的 Markdown 日记。

本版交付 **10 个基础问题＋10 个动态深入问题**、跳过、暂停、恢复、提前结束、回答修正和日记版本保存。真实采访在支持文件读写和脚本执行的 AI 客户端中进行；Python 负责本地保存与校验，无需 API 密钥。

## 快速安装（Codex）

将下面整段指令复制到支持文件读写和 Python 执行的 Codex 对话中。安装器会从 GitHub 获取完整的 `daymirror` 目录，包含 Skill 指令、脚本、模板和参考文档。

```text
$skill-installer 请安装 https://github.com/Arsen1668/DayMirror-AI/tree/main/daymirror 中的 DayMirror Skill。
检查 Python 3.10+，使用运行该 Skill 脚本的同一个 Python 安装其 requirements.txt 中的依赖。
运行该 Skill 的 demo 命令，验证合成记录的“采访 → 暂停 → 恢复 → 保存”流程。
完成后报告实际安装路径、验证结果和启动方式。
```

安装完成后，在下一轮对话中发送：

```text
$daymirror 请开始今天的反思采访。
先让我选择日记工作空间的绝对路径和 IANA 时区，然后按流程每次只问一题，完成后自动保存日记。
```

如果安装后未显示 Skill，重启 Codex 再试。Codex 支持从其他 GitHub 仓库安装 Skill，详见 [官方安装说明](https://learn.chatgpt.com/docs/build-skills#install-curated-skills-for-local-use)。Python 依赖为 PyYAML 和 tzdata；本地脚本无需 API 密钥。

其他 Agent 需要支持 Agent Skills、文件读写和 Python 执行，使用其对应的 Skill 安装入口；本版尚未逐一验证其他客户端。

## 快速演示

先将仓库克隆或解压到自己的目录。在 PowerShell 中进入仓库根目录并安装依赖，再运行演示（将 `YOUR_CLONE_DIRECTORY` 替换成实际路径）：

```powershell
Set-Location 'YOUR_CLONE_DIRECTORY'
python -m pip install -r requirements.txt
python -X utf8 daymirror/scripts/daymirror.py demo
```

命令使用明确标记的合成问答：回答 3 题 → 暂停并退出进程 → 新进程从第 4 题恢复 → 完成两轮 → 保存日记。输出中的 journal_path 是生成文件的绝对路径。每次演示使用 work/demo 中的新目录。

离线演示验证存储流程。真实的深入问题和总结由 AI 根据你的回答生成，演示题目不是固定访谈题库。

也可直接查看 [已生成的合成日记](daymirror/assets/example-journal.md) 与 [本地验收记录](docs/verification.md)。

## 开始真实采访

向有本地文件权限的 AI 客户端发送以下指令，先把 `YOUR_SKILL_PATH` 替换成仓库内 `daymirror/SKILL.md` 的绝对路径，把 `YOUR_WORKSPACE` 替换成自己选择的私密数据目录。时区 `Asia/Shanghai` 是示例，可换成自己的 IANA 时区：

```text
请读取 YOUR_SKILL_PATH，
按照 DayMirror 流程逐题采访我，记录今天。
工作空间使用 YOUR_WORKSPACE，
时区为 Asia/Shanghai。每次只问一题，完成后自动保存日记。
```

这是直接读取 Skill 的试用方式。若客户端支持安装 Agent Skills，可将 daymirror 文件夹安装到其技能目录；在 Codex 中可调用 `$daymirror`，其他客户端使用各自的调用方式。

采访中可说“跳过”“暂停”“继续”“今天先到这里，保存已有内容”“修改第 3 题”。恢复时给客户端原工作空间和会话编号；没有编号时工具优先选择最近未完成记录。

正常完成后自动保存。仅说“暂停”会保留可恢复草稿；明确提前结束会生成未完成日记。修改已保存回答时生成新版，保留旧文件。

## 依赖与验证

需要 Python 3.10+、PyYAML 6.x 和 tzdata。缺少依赖时运行：

```powershell
python -m pip install -r requirements.txt
```

运行测试与文件校验：

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 tools/validate_skill.py
python -X utf8 tools/package_release.py
```

最后一条只创建本地分发 ZIP 和清单，不上传 GitHub。打包采用固定白名单；真实数据目录、运行数据和临时文件不会进入分发包。

已实测：Windows、Python 3.10.9、PyYAML 6.0.3。代码按跨平台方式组织，其他操作系统和不同 AI 客户端尚未实机验证。

## 数据与隐私

默认数据在 private/workspace：sessions 保存 JSON 问答和进度，journals 保存版本化 Markdown，inputs 保存私密命令输入。

未知指标为 null，不用 0 代替。情绪、精力和压力只来自用户明确评分；每个非空指标引用来源问题。正文区分用户自述、主观感受和待验证的 AI 假设，建议也不会记成已执行行为。

**本地存储与本地推理是两回事。** Python 工具不联网；AI 客户端仍可能把回答和读取的文件发送给模型服务。文件为明文。详见 [隐私说明](daymirror/references/privacy.md)。

## 进一步阅读

- [v0.1 需求与验收](docs/v0.1-requirements.md)
- [Skill 工作流](daymirror/SKILL.md)
- [命令与数据接口](daymirror/references/schema.md)
- [访谈协议](daymirror/references/interview.md)

v0.2 将实现历史统计、周期报告和建议效果追踪。v0.1 已保留结构化指标与原始上下文，不自动生成周报或月报。

## 许可证

项目采用 [MIT 许可证](LICENSE)。独立分发的 `daymirror` Skill 目录也包含同一许可证。
