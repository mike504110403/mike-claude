# 邏輯 Prototype

用單份自足HTML/CSS/JS讓非工程使用者按按鈕走state模型；可離線開，不依賴CDN／真後端。頁首寫要回答的問題與假設。

邏輯放純module：reducer／explicit state machine／functions，DOM只調用它，不讓規則藏button handler。呈現領域詞標籤、相關state、合法action、變化說明與reset。自由操作加guided scenario，一步一步展示邊界而非一鍵快轉看不到轉移。

資料用合成fixture，內容經過escape，預設無持久化。要検驗persistence也只用明確scratch資源，不能意外寫production。結論說明哪些情境驗證了、哪些只是演示；復用邏輯或正式落地需要另有實現要求。
