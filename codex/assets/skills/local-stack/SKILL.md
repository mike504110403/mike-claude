---
name: local-stack
description: 依專案本機宣告啟動／停止／查詢地端全棧，供手測與跨端驗證使用。
---

# 地端棧

此技能只讀宣告並依約執行，不含任何專案預設環境。從 cwd 向上至 repo root 找 `.codex/localstack.json` 與兼容的 `.claude/localstack.json`。同一 repo 兩者皆存在、或多層宣告互相矛盾時，列出差異並停止相依動作，不能靜默挑一份。明確指定的宣告仍要確認 repo／checkout 相符。不存在就回報缺宣告，不猜 ports、帳號或 service。

執行前讀 [宣告契約](references/contract.md)。要建立新宣告可用 [無真值範本](assets/localstack.example.json)；此 example 是共享 schema 示意，實際本機宣告與 secret override 應忽略於 Git。

- `status`：只查狀態，不啟動服務。
- `up`：先查 binary／script／cwd、API routing 和 isolation；讀將執行的 script，依宣告啓動並等待 bounded readiness。
- `down`：只停本次／宣告管轄服務，預設保留資料；先核實 stop command 不夾帶 wipe。
- `wipe`／migration／環境等價設定中有破壞或 DB mutation：列出具體動作、影響與還原方式，依 session 授權確認人類同意；未授權不得執行。sandbox 可執行不代表人類已同意。

非零 exit 是失敗；保留遮罩後原始輸出，不編造成功。readiness 用宣告的 exit／字串／其他可判定條件，有限次重試後回報未就緒，不放寬判準。前端覆蓋 API env 與 proxy 後，還須透過實際 request 確認地端獨有回應；首頁 200 不足以證明 API 位址。

宣告含 prod_data 時讀 lottery-proddata 或其明示政策，確認副本鮮度、版本／SQL mode 等價與對外服務停用。不可把 migration 操作當 up 的預設附帶步驟。

就緒後回報 URL／port／健康狀態、frontend env_override、取得測試帳號的本機方式（不印秘密）、known_limitations、isolation 對外連線。App 可用 open_in_codex 時開宣告中的前端 URL供 Mike 手測，否則回 URL。

環境不足時依序降為只起後端，再靜讀＋跨端對照；每降一階在 wip.md 記原因、替代證據、未驗流程與補驗命令／腳本。不能把靜讀稱為 runtime 通過。
