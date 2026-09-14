# DSH-CFIPS

每日自动抓取的 **Cloudflare 优选 IP 订阅源**，电信 + 多线，IPv4 only。

## 订阅地址

```
https://raw.githubusercontent.com/chanriver/dsh-cloudflare-ips/main/DSH-CFIPS.TXT
```

## 数据来源

1. <https://api.uouin.com/cloudflare.html>（麒麟域名监测，每 10 分钟更新）
2. <https://www.wetest.vip/page/cloudflare/address_v4.html>（微测网，每 15 分钟更新）

合并去重后写入 `DSH-CFIPS.TXT`，格式为 `IP:PORT`，端口统一 `443`（Cloudflare HTTPS 标准端口）。

## 自动更新

- [GitHub Actions](./.github/workflows/update-ips.yml) 每天 **UTC 03:00**（北京时间 11:00）抓取一次
- 内容有变化才 commit + push，避免无效提交
- 也支持手动触发：Actions 页 → `Update DSH-CFIPS` → `Run workflow`

## 本地运行

```bash
python3 fetch_cf_ips.py
# 生成 / 更新当前目录下的 DSH-CFIPS.TXT
```

依赖：仅 Python 3.8+ 标准库，无需 `pip install`。

## 筛选规则

| 线路   | 是否保留 |
| ------ | -------- |
| 电信   | ✅        |
| 多线   | ✅        |
| 移动   | ❌        |
| 联通   | ❌        |
| IPV6   | ❌        |

如需调整编辑 `fetch_cf_ips.py` 顶部的 `KEEP_LINES` 即可。

## 文件结构

```
.
├── DSH-CFIPS.TXT              # 订阅源（自动生成）
├── fetch_cf_ips.py            # 抓取脚本
├── .github/workflows/         # GitHub Actions 配置
└── README.md
```
