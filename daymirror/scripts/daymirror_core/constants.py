SCHEMA_VERSION = 1
TOTAL_QUESTIONS = 20

BASIC_QUESTIONS = [
    "今天你主要做了哪些事情？最重要的三件是什么？",
    "今天的时间大致如何分配？可以按工作、学习、休息等活动描述。",
    "今天原本计划完成多少项任务，实际完成多少项？具体进展如何？",
    "今天什么时候最专注？如果记得，深度专注大约持续了多少分钟？",
    "今天有哪些拖延、分心或受阻的情况？请举一个具体例子。",
    "今天的情绪有哪些变化？如果愿意，请分别给情绪和压力打 1–10 分；情绪分越高越积极，压力分越高压力越大。",
    "今天的睡眠、饮食、运动和精力如何？可提供睡眠小时数、运动分钟数，以及 1–10 的精力评分；不清楚的可以不填。",
    "今天学习了什么，或者取得了什么进展？",
    "今天与他人的交流或外部事件对你产生了什么影响？",
    "回顾今天，你最满意和最希望改进的事情分别是什么？",
]

# key: (number type, inclusive minimum, inclusive maximum or None)
METRIC_RULES = {
    "sleep_hours": ("number", 0, 24),
    "focus_minutes": ("number", 0, 1440),
    "planned_tasks": ("integer", 0, None),
    "completed_tasks": ("integer", 0, None),
    "mood": ("integer", 1, 10),
    "energy": ("integer", 1, 10),
    "stress": ("integer", 1, 10),
    "exercise_minutes": ("number", 0, 1440),
}
SUMMARY_LISTS = ("events", "reflections", "learnings", "obstacles")
CLAIM_KINDS = {"reported_fact", "self_assessment", "hypothesis"}
KIND_LABELS = {
    "reported_fact": "用户自述",
    "self_assessment": "主观感受",
    "hypothesis": "AI 假设，待验证",
    "suggestion": "AI 建议",
    "user_commitment": "用户表达的行动意向",
}
