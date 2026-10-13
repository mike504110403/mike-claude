---
name: graft
description: 已建 graft 圖的 repo 中，先查圖找程式位置、呼叫鏈或影響面；圖不存在或失效時退回 rg。
---

# Code graph 探路

啟用前確認目前 checkout 的 `graft/` 圖檔／manifest 存在，再確認本機 graft CLI 或 MCP 可用及版本／help。不存在不自動 init、install 或新增 hook，直接用 rg，並回報未用圖。

有可用且新鮮的圖時先圖後 rg。按需求選 `ask`（位置與概念）、`grep`（所有匹配）、`skeleton`（檔案介面）、`callers`／`blast`（呼叫與影響）、`map`（結構），旗標以該版本文件為準；MCP 工具名稱以本回合暴露為準。lexical ask 可用英文 symbol/question，無結果改精確 symbol 搜尋，不反覆換句問。

先查圖的 commit、生成時間與 freshness/check 能力，對照 git diff。worktree 各自有 checkout 狀態；其他 worktree 的圖不能直接當證據。圖已過期、缺檔、span 不符或工具不支援 freshness 時，明示限制、以 source 查證。修改 code 後使用 repo 已記錄的建圖命令；若 repo 依賴 LSP 邊，保留其 build/LSP 設定，避免裸 build 刪邊。沒有明確命令時先查 help／repo 約定，不能照搬舊旗標。

`--no-refresh` 僅在已核實當前版本自動 refresh 會損失所需邊時使用，並安排顯式重建。不得同時宣稱禁刷新與圖必然最新。router method-value／interface 注入可能無 callers，配合 graph grep／rg 查註冊點。影響面證據最後核實 source `檔案:行號` 及被破壞的不變量。

不執行外送 source 的 deep/LLM build，除非使用者另行授權。tokens-saved 是工具估算，只有實際回報才可引用；不宣稱版本未提供的精確節省。
