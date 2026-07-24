---
name: bruno-v3-env-editor-bug
description: Bruno 3.5.3 的環境編輯器 Save 會把環境 .bru 檔刪掉且寫不回去，環境變數一律直接改檔案、不走 UI
metadata: 
  node_type: memory
  type: reference
  originSessionId: 22395b83-1dde-4db0-b7e5-b619b1e48477
  modified: 2026-07-22T08:24:58.310Z
---

2026-07-22 實測（Bruno 3.5.3, gold-price 專案）：在 app 內的環境編輯器按 Save 會報錯，且把磁碟上的 `environments/*.bru` 刪掉不寫回；UI 裡的環境列表殘留（app 快照 `~/Library/Application Support/bruno/ui-state-snapshot.json` 記錄環境選擇路徑），刪也刪不掉。用面板的 import 匯入 `.example` 也會製造與實體檔撞名的幽靈環境。

**處置方式：** 環境變數一律直接編輯 `bruno/environments/*.bru` 檔案（大腦代改或手動），完全不要用 UI 的環境編輯器 Save / import。改完 Bruno 會自動重載。token 類變數用 `vars:secret [...]` 區塊標 secret（值不落檔）。若 app 狀態髒掉：退出 Bruno → 修 `ui-state-snapshot.json` 的環境路徑 → 重寫環境檔 → 重開。

相關：[[api-testing-tool-bruno]]。若 Bruno 升版後 UI 修好可刪本記憶。
