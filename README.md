# removeads DNS 广告规则聚合

本项目自动下载多个上游广告域名列表，统一解析、规范化、去重，并生成可供 AdGuard Home 使用的 DNS 过滤规则。项目由 GitHub Actions 运行，无需在本地执行。

## 上游来源

- [Loyalsoldier surge-rules/reject](https://raw.githubusercontent.com/Loyalsoldier/surge-rules/release/reject.txt)
- [anti-AD](https://raw.githubusercontent.com/privacy-protection-tools/anti-AD/master/anti-ad-domains.txt)
- [AdGuard DNS filter](https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt)

工作流每天北京时间 **04:00** 自动更新，也可在 Actions 页面手动运行。

## 输出文件

- `output/adguard-dns.txt`：AdGuard DNS 过滤语法（`||example.com^`）。
- `output/domains.txt`：排序后的规范化域名列表（开头为注释元数据）。
- `output/report.json`：来源下载状态、规则数量和过滤统计。

构建少于 50,000 条规则时会失败，且不会替换已有输出。单一来源故障不会阻止其他成功来源生成结果。

## 在 AdGuard Home 中订阅

进入 **过滤器 → DNS 封锁清单 → 添加封锁清单 → 添加自定义列表**，填写本仓库 `output/adguard-dns.txt` 的 Raw URL：

```text
https://raw.githubusercontent.com/<用户名>/<仓库名>/<分支名>/output/adguard-dns.txt
```

将占位内容替换为实际的用户名、仓库名和分支名，然后保存并更新过滤器。

## 自定义规则

- 在 `allowlist.txt` 中每行添加一个域名，可排除该域名及其所有子域名。
- 在 `blocklist.txt` 中每行添加一个域名，可强制加入结果。blocklist 在 allowlist 后应用，因此相同条目以 blocklist 为准。
- 可使用 `#` 开头的注释；IDN 会转换为 ASCII/Punycode。修改后提交，手动触发工作流或等待每日更新。

## 故障排查

1. 在仓库 **Actions** 页面打开失败的 “Update DNS rules” 运行并查看 “Build rules” 日志。
2. 检查上游 URL 是否可访问，以及 `output/report.json` 中各来源最近一次成功构建的状态和计数。
3. 如果触发 50,000 条安全阈值，通常是上游不可用或格式发生变化；不要绕过阈值，应先检查下载日志和来源内容。
4. 如果 Action 无法推送，确认仓库的 Workflow permissions 允许读写，并且分支保护规则允许该工作流更新分支。
5. 自定义域名未出现时，检查格式是否有效，以及是否被 `allowlist.txt` 排除。

## 版权说明

所有上游规则的版权及许可归各自原作者所有。本项目不创作或主张拥有这些规则，仅进行自动整理、格式转换和发布；使用时请同时遵守各上游项目的许可条款。
