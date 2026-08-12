---
name: lottery-proddata
description: 彩票群的地端 prod 資料副本——查生產環境資料、local-stack 起棧、對 prod 形狀做任何驗證時一律用它，不連 RDS。Mike 說「查 prod 資料」「用生產資料測」或彩票工程需要真實資料形狀時使用。
---

# /lottery-proddata — 彩票地端 prod 資料副本

## 鐵律

**查生產資料、驗證 migration、實測資料形狀 → 一律先用地端副本,不連 RDS。** 只有「必須是此刻最新值」的查詢（對帳、事故當下狀態）才連生產,且唯讀。

## 連線參數

| 欄位        | 值                                                                                                                                                                                                         |
| ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Host / Port | `127.0.0.1` : `3310`                                                                                                                                                                                       |
| DB          | `lottery`(內容=m5_prod 副本)                                                                                                                                                                               |
| 帳密        | `root` / `0000`                                                                                                                                                                                            |
| 容器        | `lottery_mysql_dev`(docker exec 路徑:`docker exec lottery_mysql_dev mysql -uroot -p0000 --default-character-set=utf8mb4 lottery -e "..."`;中文欄位/註解必帶 `--default-character-set=utf8mb4`,否則顯示 ??) |

## 副本血統(判斷時效用)

- 來源:`slave-wx-prod-rds...ap-east-1.rds.amazonaws.com` 的 `m5_prod`,**2026-08-14 20:54** mysqldump(no-locks 模式,跨表可能有秒級錯位)。
- **匯出時排除**:分區/備份表 ＋ `crawler_sync_task`、`crawler_sync_member`、`game_recommendations`(此三表已由 migration 在地端重建為**空表**——查 M6 任務/推薦資料時記得地端是空的,要真值連生產)。
- 76 張表、user_rebate 50,355 列、users 2,472 列;migration ledger 隨副本帶入(=prod 真實帳)。
- 快照時 prod 已知狀態:GA 自助綁定開關=開、zimu808 停用+佔位密鑰、跨合營商髒帳號 30 筆(裁示:不修資料程式適用)、超額鏈 539 筆。

## 環境等價性(與 prod 的已知差異)

- **GLOBAL sql_mode 已設 `NO_ENGINE_SUBSTITUTION`**(=prod,非嚴格)。⚠️ **lottery_mysql_dev 容器重啟會失效**,重啟後補:
  `docker exec lottery_mysql_dev mysql -uroot -p0000 -e "SET GLOBAL sql_mode='NO_ENGINE_SUBSTITUTION';"`
- 本地 MySQL 版本 **26.7**(mysql:latest)vs prod **8.4.8**——schema/資料層驗證可信;**版本敏感的 DDL/ALTER 行為驗證要另起 `mysql:8.4` 拋棄容器**(慣例做法,勿在此副本上下 ALTER 測行為)。
- 已量測等價項:collation 全庫僅 utf8mb4_unicode_ci/utf8mb4_0900_ai_ci 兩種、user_rebate 七欄 COMMENT/型別/DEFAULT 與 model tag 逐字相符。

## 重新整備(副本過期要刷新時)

1. Mike 用 DBeaver dump(Local Client=`/opt/homebrew/Cellar/mysql-client/9.7.1`,Execution=Normal no locks)或 `docker run --rm mysql:8.4 mysqldump -h <slave RDS> ...` 出檔到 `~/Documents/kabo/lottery/`。
2. 停四服務(platform/forever/game-hub-v2/game-core,pid 檔在 `localstack/run/pids/`)。
3. `DROP DATABASE lottery; CREATE DATABASE lottery DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;` → nohup 脫離式匯入(4.7GB 約 6 分鐘;**不可**用會被 10 分鐘上限砍掉的前景/背景殼)。
4. **必做善後**:①`SET GLOBAL sql_mode='NO_ENGINE_SUBSTITUTION'`;②**de-fang**:`UPDATE providers SET status=0 WHERE status=1;`(prod 資料帶真第三方商,不關會對外拉單);③匯出排除表的 migration 記錄刪掉讓程式重建:`DELETE FROM migration_record WHERE version IN ('20260709_init_crawler_sync','20260709_add_crawler_sync_task_status_index','20260710_add_crawler_sync_task_fresh','20260813_add_crawler_sync_task_site_id','20260717_add_sync_member_fail_reason','20260810_add_m6_bank_sync','20260709_add_game_recommendations','20260720_add_game_recommendation_interval_group_status');`
5. `localstack/up.sh` 起棧(它會再跑一次 de-fang,冪等)。

## 其他注意

- 副本裡是真實會員資料(帳號、銀行卡、餘額)——**只留在地端,任何輸出/截圖注意遮罩**,不進 git、不上傳。
- 起 forever 前 de-fang 必須已生效(providers status=1 =0 筆),否則會對 AG/OKAI/CR 真端點發請求。
- dump 檔用完可刪(佔 4.7GB);刷新程序以本 skill 為準。
