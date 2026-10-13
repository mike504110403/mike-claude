---
name: bruno-sync
description: 維護 Bruno 純文字 API collection；API 改動且已有 bruno/ 時增量同步，使用者要求才初次匯入。
---

# Bruno Collection 同步

Bruno 同步是直接讀寫 repo 的 `.bru`，不需 App、CLI 或 MCP。自動條件是此次 API 有變且 repo 已有 `bruno/`；沒有 collection 時不自動創建，只有使用者要求全量匯入才做。

先固定 diff base／範圍，找有效 route、middleware、handler及DTO；code 是事實，OpenAPI 用來對照。先讀已有 collection與人工內容，再按 [同步政策](references/policy.md) 合併。新增／修改／刪除 request 都須對照來源 route，維護 MANIFEST，差額逐條解釋。

範例不含真實帳號／token／secret；`.bru.example` 只放空 secret 變數與公開結構。真 environments/*.bru 以及可能回寫 token 的 collection.bru 必須排除 Git；不讀 auth/session/credential files 來做全文比對。檢查 diff／追蹤檔案／可疑 secret 名稱與值模式，發現疑似值只回報檔案位置和遮罩。

外部前提：需要 Bruno-specific WS、腳本API、auth遞迴繼承或語法檢查時，確認已安裝版本或其官方文件；不能猜。沒有驗證工具仍可完成檔案同步，但語法／runtime標未驗。要跑 request 或登入時另依 local-stack與使用者授權，不能因同步檔案就對外送 request。

回報新增／修改／刪除 endpoint、route數對帳、例外、保留人工內容、檢查證據與未驗限制。review／commit／merge依本次 lane與feature-flow，不自動push。
