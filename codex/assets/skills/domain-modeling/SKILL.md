---
name: domain-modeling
description: 釐清領域詞彙／概念關係並依授權維護 glossary 或 ADR。
---

# 領域模型

只有要改變／釐清domain模型時用本技能，單純讀CONTEXT不是新增模型需求。先讀現有CONTEXT-MAP、對應CONTEXT與ADR；單context採root CONTEXT.md，多context按map定位，未知context才問。

用具體scenario挑戰模糊詞、同義詞與概念關係。使用者描述與code矛盾時查檔案:行號，區分「目前行為」與「目標模型」，再確認權衡；不要把觀測到的code自動當領域正確答案。

記錄已確認術語到使用者指定／repo既定位置，檔案懶建立，沿用 [references/formats.md](references/formats.md)。CONTEXT只含領域定義與避免同義詞，不塞implementation、待辦或spec。可逆／顯而易見決策不用ADR；只有難逆、沒有context會令人意外、且確有替代權衡時提ADR。

保存文件屬於當前授權工作；若只要求在chat討論，不自動創建repo文件。未決說法不落為accepted decision。
