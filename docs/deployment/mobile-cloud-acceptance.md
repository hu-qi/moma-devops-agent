# 移动云部署与验收（2026-10-09）

DevOpsPilot已在组委会账号的华北-北京3实例运行，实例内组件验收通过。外部浏览器尚未通过，不能声称所有评审客户端均可访问。

## 运行位置

- 实例：devopspilot-console，5f54db32-f8b0-45eb-8775-dd8e617e0eaa，Ubuntu24.04.4，Python3.12.3，2核4GB，40GB系统盘。
- 入口：http://36.137.203.138:3000/，Nginx仅允许已报备103.88.46.0/24与本机；后端127.0.0.1:8080。
- 代码：/opt/devopspilot；systemd：devopspilot.service；运行用户devopspilot，开机启动。
- 凭据：/etc/devopspilot/environment，root:devopspilot，0640；项目.env仅为指向该文件的链接。没有写入Git。
- 数据：/var/lib/devopspilot/state.console.db（项目、聊天与任务调度）；state.db为交付状态库，当前没有新建云端交付任务，状态API的db_exists为false，不伪造交付完成记录。
- 备份：/var/lib/devopspilot/backups/console-20261009.db，使用SQLite .backup生成，非运行中直接复制文件。

## 实际验收

| 项目 | 结果与边界 |
|---|---|
| systemd | 重启后active，非root用户运行 |
| 页面 | 实例内Nginx3000返回35760字节Web页面；API验收脚本确认HTTP200及品牌内容 |
| 运行时 | 固定OpenJiuwen提交6f3a33fbb93aece65105c477c573057fead0e8dd安装成功，包元数据0.1.18；runtime API报告已安装 |
| GitHub | hu-qi/moma-devops-agent真实同步，3个Issue，15条CI记录，来源remote_api |
| AtomGit | huqi/moma-devops-agent真实读取成功，当前0个Issue；不虚构空仓库任务 |
| MoMA | deepseek-v4.1-flash真实回答成功，首次读取验收usage209 tokens；HTTP API验收再次成功 |
| 模型配置 | GLM-5.3与Qwen3-32B等角色配置保留；本次问答不证明每个角色都完成新的Live交付 |
| 持久化 | 重启前后2个项目、2条聊天记录保留 |
| 备份 | SQLite pragma integrity_check返回ok；尚未做覆盖生产库的恢复演练 |
| 外部访问 | 普通curl、排除HTTP代理的curl均Empty reply；ego-lite浏览器ERR_HTTP_RESPONSE_CODE_FAILURE。未进一步重试，未改安全组 |
| 本地回归 | 41/41通过；独立于云端验收，不能混用证据层级 |

原始云端JSON：/var/lib/devopspilot/cloud-live.json（真实读取），/var/lib/devopspilot/cloud-acceptance.json（页面与API组件验收）。本仓库JSON为依据VNC实读制作的摘要，未假称已下载原始云端JSON。

## 版本与证据

源码通过GitHub固定提交归档e5b81cb2680fd9a1a328c2419fd77ce22e2a9408解压。随后从16ef9ed归档获取部署与验收脚本，手工修复目录权限；核心应用未改。归档不含.git，因此状态API的commit_sha为unknown，不能用该字段伪造当前Git版本。两个核心文件云端sha256sum与本地一致：

- src/devopspilot/web/console.html：46048aaf4f2ba24ad918d8844e2f56edc0e3c4f84342a204708e1a2ac29c77a7
- src/devopspilot/web/console.py：aeba6be5dfc6bcb222dd9e0b49f1c9871a8e58b5db41df8789b79788815d05b5

截图：[云端验收](../evidence/mobile-cloud-acceptance-2026-10-09.png)。部署分支codex/mobile-cloud-deployment；安装脚本已修复umask077导致包目录不可读和工作目录不可遍历的问题。

## 运维与接入

```sh
systemctl status devopspilot --no-pager
journalctl -u devopspilot -n 100 --no-pager
curl -f http://127.0.0.1:8080/api/status
curl -f http://127.0.0.1:3000/
```

支持从已批准网段SSH连接后，用SSH隧道进行私密验收；当前客户端SSH在认证前被关闭，不能声称该隧道已打通。评审客户端若不在103.88.46.0/24，应先确认组委会接入方式与重新报备要求，不能直接扩大公网规则。当前控制台没有完整用户登录鉴权，受限入口也不等于可向所有公网开放写接口。

EIP到期2026-10-25 09:37:38，ECS到期2026-11-08 14:18:22，未开启自动续费。本次ECS与磁盘订单应付¥0、VPC免费；现有EIP费用另计，未擅自续订。MySQL未接入，未新增数据库资源。

本次完成云部署与组件真实读取验收，不替代新的Issue→编码→PR→CI完整Live交付签收。已上传的大赛作品包保持原样，云部署记录另行补充，未再次覆盖正式提交。
