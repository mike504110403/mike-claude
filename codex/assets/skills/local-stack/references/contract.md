# 本機宣告契約

宣告檔不執行為 code，先 JSON parse。以下約定支持既有 `commands.<action>.cmd` 形狀；既有專案 schema 不同時讀其文件核對，不自行猜欄位。缺必要欄位、空命令或錯誤型別就停止並列缺項。

| 欄位 | 契約 |
| --- | --- |
| `commands.up/down/status/wipe` | 各含 `cmd`、`cwd`、`path_type`（relative/absolute）與 `shell`；只有要求的動作必須存在。cmd 是該 shell 的命令字串，先讀被呼叫 script。 |
| `cwd`／`path_type` | relative 對宣告所屬 repo root 解析，不能對 agent cwd 猜；absolute 須核實本機存在。每次命令顯式設定 workdir。 |
| `ready_check` | `cmd`／cwd/path_type/shell、`success_criteria`、有限 `attempts`／`interval_seconds`／`timeout_seconds`；exit/string 等判準須可判定。沒有就不能宣稱 up 成功。 |
| `services` | 名稱、URL/port、健康檢查與本機依賴；由宣告取值，不能看到 port 被佔用就殺未知 process。 |
| `frontend` | `url`、啟動 script/cwd、`env_override`（環境變數映射）、proxy/API 說明；值須與實際生效優先序核對。 |
| `credentials` | 本機 secret 的取得方式／引用；不把值印到回報，也不能把 credential file 複製進產物。 |
| `isolation` | 所有 outbound connections、可觸發的外部副作用與停用機制；未知／正式 target 未隔離時停止有副作用流程。 |
| `known_limitations` | 地端功能限制與健康告警允許清單；要能區分環境限制與產品錯誤。 |
| `prod_data` | snapshot 取得時間／來源摘要、schema與migration ledger、DB版本／SQL mode、equivalence_cmds／rehearsal_checks與refresh_policy。命令仍受人類授權與secret約束。 |

若用本機 override：先列出它的路徑與明確 merge/precedence 契約；沒有契約就不合併。overlay只提供本機值，不能靜默替換 isolation、readiness 或安全限制。宣告可能含秘密，輸出只留欄位名稱與遮罩摘要。

readiness 命令只讀；若內含 migration、seed 清表、GLOBAL 設定或外部寫入，應拆分成已授權動作與只讀檢查。保留 stdout/stderr／exit證據，重試上限到達即停止。不要重試有副作用的 up 命令來取代 readiness polling。
