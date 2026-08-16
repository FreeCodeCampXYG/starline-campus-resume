# DEV_STATE

## 当前目标

将现有简历 Skill 改造为可独立发布的 `starline-campus-resume`，清理旧品牌和推广资源，并吸收 `amlei/amlei-resume` 已核对的事实源、岗位投影和浏览器编辑工作流经验。

## 已完成

- 从本地安装副本建立独立源码目录 `starline-campus-resume`。
- 将 Skill 身份、触发描述和界面元数据迁移到 Starline 命名空间。
- 增加事实源与岗位投影说明、公开 README 和基础包校验脚本。
- 明确当前渲染器以 `resume-data.json` 为输入，Markdown 作为 Agent 可读事实入口，不虚假宣称任意 Markdown 自动解析。
- 未复制参考项目的图片、CSS、代码或文字。
- 已将个人 Fork 重命名为 `FreeCodeCampXYG/starline-campus-resume`。
- 已创建并推送功能分支 `codex/starline-campus-resume`，尚未合并到 `main`。
- 已删除旧个人资源、IDE 配置和生成报告；保留上游 MIT 版权归属并追加 Starline 修改版权。
- 已增加标准 PR 模板和 Bug/Feature Issue 模板，明确验证、隐私和事实准确性检查项。
- 已创建指向 `main` 的 Pull Request，并设置 GitHub Topics；未创建 Git 版本 tag。
- 已补充事实档案/岗位投影三层契约、示例数据和 `validate_profile.py`，并将渲染临时目录改为 Starline 命名。

## 核心文件

- `SKILL.md`
- `README.md`
- `manifest.json`
- `agents/interface.yaml`
- `references/profile-and-projection.md`
- `scripts/validate_skill.py`
- `scripts/render_resume.py`

## 已知风险

- 本地安装副本不是 Git 仓库；远程功能分支通过 GitHub Git API 从原 `main` 树构建，历史通过远程父提交保留。
- Windows Edge 无头打印可能生成 PDF 后在临时 profile 清理阶段报锁文件错误；这属于运行环境问题，需在发布前单独验证。
- 远端 `main` 当前仍有重复的 `LICENSE` 与 `LICENSE.txt`，本次优化提交会保留 `LICENSE` 并删除重复文件。

## 下一步

1. 创建并检查事实档案优化 PR。
2. 合并后验证远端发布工作流包含 `validate_profile.py`。
3. 如需发布 Git 版本 tag，另行确认版本号、注释和 Release notes。
