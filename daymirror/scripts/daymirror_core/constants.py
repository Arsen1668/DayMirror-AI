SCHEMA_VERSION = 1
TOTAL_QUESTIONS = 20

# Both rounds use AI-generated questions saved one at a time.

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
