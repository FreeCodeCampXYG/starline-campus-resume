# 事实档案与岗位投影契约

## 设计目的

`profile.json` 是跨岗位复用的客观事实层；`projection.json` 是一次求职方向的选材与强调层；`resume-data.json` 是现有渲染器消费的最终快照。三者分开，避免换岗位时复制出多份互相漂移的主简历。

## 事实档案 `profile.json`

```json
{
  "version": 1,
  "updated_at": "2026-08-16T09:00:00+08:00",
  "identity": {"name": "姓名", "location": "城市"},
  "facts": [
    {
      "id": "project-qc",
      "kind": "project",
      "summary": "完成某项目的客观描述",
      "period": {"start": "2025.01", "end": "至今"},
      "status": "confirmed",
      "visibility": "public",
      "evidence": ["interview-2026-08-16"]
    }
  ],
  "capabilities": [
    {"id": "cap-api", "label": "接口开发", "proven_by": ["project-qc"]}
  ]
}
```

事实必须是中性、可解释的描述，不直接写成简历 bullet。`status` 只能是 `confirmed`、`needs_review` 或 `draft`；`visibility` 只能是 `public` 或 `private`。已确认事实也必须保留至少一个 `evidence` 引用，能力必须通过 `proven_by` 关联项目或经历事实。

## 岗位投影 `projection.json`

```json
{
  "version": 1,
  "profile_version": "2026-08-16T09:00:00+08:00",
  "target": {"role": "AI 应用开发", "company_type": "医疗信息化"},
  "selected_fact_ids": ["project-qc", "cap-api"],
  "excluded_fact_ids": [],
  "emphasis": ["智能体与工作流", "接口工程化", "证据驱动表达"],
  "resume_data": "resume-data.json",
  "user_confirmed": true
}
```

投影只能选择存在、`public`、非 `needs_review` 的事实。`profile_version` 必须等于事实档案的 `updated_at`；事实档案更新后，旧投影必须重新确认，不能静默改写已有简历文案。最终生成前先校验投影，再将选中的事实转换为 `resume-data.json`。

## 写入和更新规则

1. 从对话、项目资料或链接提取的新事实先标为 `draft`，展示给用户确认后再改为 `confirmed`。
2. 用户修改客观事实时更新事实层版本，不自动重写下游 bullet；相关投影标记为需要重新确认。
3. 岗位变化只新建或复制投影，不复制事实档案。
4. `private`、`needs_review` 和 `draft` 内容不得进入公开 PDF、HTML、README、示例、日志或发布包。
