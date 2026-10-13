---
name: lottery-proddata
description: 彩票資料形狀／生產副本驗證時採地端副本政策；本技能不含連線、帳密或快照真值。
---

# 生產資料的地端副本

查資料形狀、驗 schema／migration 相容性、local-stack 起棧時優先使用已隔離的地端副本，不連正式 RDS。本技能只持有政策；連線、帳號、snapshot、版本、SQL mode 與刷新命令由該 repo 的本機宣告提供，不讀任何 credential file 來填共享範本，不把來源機器真值寫入 Git。

開始前確認：副本實際在地端、來源／匯出時間、完整／排除表清單、schema與migration ledger、需要的資料分布、DB引擎／版本、SQL mode／collation等環境差異。缺鮮度或版本證據就標未知，不能稱為「與 prod 等價」。資料 shape 檢查與版本敏感 DDL 必須分別陳述適用範圍。

副本含真會員、銀行卡、餘額等資料；查詢以最少必要欄位與聚合為主，輸出／trace／截圖遮罩，dump與中間檔只留已授權本機位置，不進 Git、不上傳。先確認 providers、排程、通知、付款與其他外連副作用已依本機 isolation 停用，否則不能啟動會對外寫入的程序。

刷新／drop／truncate／重匯／修改 migration ledger／GLOBAL設定或 DDL 屬實際資料 mutation：先列出命令目的、影響、備份／還原方式，取得具體人類授權後才執行。不能因「地端副本」就跳過；不得搬歷史 migration ID 清單或盲刪 ledger。若 dump 排除了表，先核實 schema、ledger與應用版本，再由使用者裁定重建策略。

只有需求確實必須取得「此刻最新值」且使用者明確授權生產查詢時，才能另行核實 read-only 連線和查詢範圍；不能拿地端環境授權當作正式環境授權。無法讀最新值時明說副本時間限制。

回報副本鮮度、資料形狀／版本證據、已知差異、隔離狀態、查過／未查項和是否需刷新；不回報帳密真值。
