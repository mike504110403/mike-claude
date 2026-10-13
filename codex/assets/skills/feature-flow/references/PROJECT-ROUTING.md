# 跨裝置專案與驗證路由

已在 repo cwd 的工作，先讀該 repo AGENTS/本機宣告。收到專案代號而沒有 cwd 時，依序找：使用者指定的 registry；CODEX_HOME（未設才 ~/.codex）下 PROJECTS.local.md；已知 source repo 的 .codex/projects.local.md。沒有唯一匹配才向 Mike 要一次本機路徑，不猜代號、不依賴未部署全域檔。

可複製 [PROJECTS.example.md](PROJECTS.example.md) 建本機 registry，依範本選目的地及精確檔名；真實路徑、環境與私人基線不進 Git。每台只改自己的 local mapping，Git 版控範本與 repo 可攜規則。位於 Git repo 的 local 宣告依全域精確忽略規則核實；repo 外的 registry 保留本機，不在無 repo 的目錄執行 git check-ignore。registry 指向 repo 後再核實 git root、主幹、remote、commands 及目前 branch，不以舊 snapshot 推論。

驗證 commands 的權威：repo AGENTS/已讀過的 build scripts與版本控制宣告優先，local registry 只給線索。基線至少附指令、適用環境、失敗 family、核對 commit及輸出位置；基線紅不等於豁免。新增紅阻擋驗收，已存在紅列驗證限制/ledger；若無法區分新舊，不能把紅說成成功。

source dirty/ahead 保留，主幹 sync 依 /sync-dev。服務需要本機設定時按 /local-stack 的既有宣告讀取，不自動造帳號、ports 或啟動 dependencies。
