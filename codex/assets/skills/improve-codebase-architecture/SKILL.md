---
name: improve-codebase-architecture
description: 找有實證的 deepening 候選，產可比較的視覺報告並按使用者選擇深化設計。
---

# 架構深化候選

先限定使用者點名模組／痛點；沒有方向時用近期git歷史找常變區域，不能全庫泛掃。讀CONTEXT／ADR，用codebase-design語彙看真實callers與依賴；有新鮮graft圖先圖再source。可用原生readonly探路代理時依自足brief委派，不假定Explore工具名。

每個候選要有source檔案:行號、caller／interface複雜度證據、deletion test、變化如何集中與真實收益。沒有證據的只標Speculative，不能當既有問題／直接改造。與ADR衝突時說明實際摩擦為何足以重審。

產自足HTML到用戶指定位置或OS temp（Python tempfile可攜解析），不要把僅供討論的report塞repo。內嵌CSS/SVG或可離線圖，避免CDN成為展示前提。每張card含files、problem、solution、locality／leverage收益、before/after圖與Strong／Worth exploring／Speculative評級。給最推薦候選與理由，但先不承諾新interface或實作。

用App文件／browser工具可展示則打開，否則提供路徑。讓使用者選擇候選後用grilling逐題約束；記錄glossary／ADR僅在已要求保存時依domain-modeling。探索alternative interfaces才讀codebase-design的design-it-twice。此技能是調查與設計，不能把「review架構」當全庫refactor授權。
