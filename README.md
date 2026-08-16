# Starline Campus Resume

基于事实证据的中文/英文求职简历工作台：从访谈和旧简历提取素材，按岗位方向生成可编辑 HTML 与本地 A4 PDF，并用确定性脚本检查结构、证据和排版约束。

## 能力

- 从零访谈：一次只问一个问题，维护确认事实和证据链；
- 旧简历导入：支持 PDF、DOCX、TXT 和 Markdown 文本提取；
- JD 定制：建立“要求 → 证据 / 缺口 → 简历位置”映射；
- 岗位投影：同一事实源适配不同目标岗位，不复制出互相漂移的主简历；
- HTML/PDF：生成单栏、文本型 A4 PDF 和可本地编辑 HTML；
- 多主题：明确要求时生成六套核心主题或六套参考预设；
- 本地隐私：不调用云端 OCR、模型或字体服务，不包含头像、二维码、推广图和远程资源。

## 参考与原创边界

本项目参考 `amlei/amlei-resume` 公开 README 中的产品思路：长期画像与岗位简历分层、Markdown 作为可读事实入口、浏览器就地编辑、同一份经历投影到多个岗位方向，以及导出前的人工作确认。

本项目没有复制其图片、CSS、代码或文字；当前渲染器的事实输入仍是 `resume-data.json`，Markdown 需要由 Agent 按 [`references/profile-and-projection.md`](references/profile-and-projection.md) 转换后再验证。浏览器就地编辑后的事实回写也需要人工确认，避免把排版草稿误当成事实。

## 快速开始

Python 3.10+ 是基础环境。`pypdf` 仅是没有 Poppler 时的 PDF 文本提取回退依赖：

```powershell
py -3 -m pip install -r requirements.txt
py -3 scripts\validate_resume.py resume-data.json
py -3 scripts\render_resume.py resume-data.json --theme tech --output-dir output
```

只生成 HTML：

```powershell
py -3 scripts\render_resume.py resume-data.json --theme tech --html-only --output-dir output
```

PDF 生成还需要 Chrome、Chromium 或 Edge；完整 PDF 验收推荐安装 Poppler（`pdfinfo`、`pdftotext`、`pdffonts`）。没有浏览器时应交付已验证 HTML，并明确说明 PDF 缺少本地渲染器。

## 输出与隐私

默认输出一份 PDF、对应 HTML 和验证报告。访谈账本、来源提取文本和 `resume-data.json` 可能包含联系方式、私人备注或原始证据，不应直接公开。脚本只处理本地文件，不上传个人材料；扫描件 OCR 必须经过用户明确同意，并使用用户指定的本地工具。

## 不做什么

不承诺 ATS 分数、面试结果或招聘结果；不处理学术 CV、资深高管履历、作品集网站、求职信、职位代投；不虚构经历、数字、技术栈或关键词。

## 验证

```powershell
py -3 scripts\validate_skill.py .
py -3 scripts\validate_resume.py path\to\resume-data.json
py -3 -m py_compile scripts\*.py
```

最终 PDF 仍需逐页检查裁切、孤行、重叠、异常空白和中文字体嵌入。PDF 文件存在不等于最终验收通过。
