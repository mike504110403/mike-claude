---
name: bruno-sync
description: 把專案 API 整理成 Bruno collection。repo 沒有 bruno/ 時做初次全量匯入；已有 bruno/ 時做增量同步（git diff 找 API 改動）。工程任務收尾偵測到 API 改動且專案有 bruno/ 時大腦自動執行；Mike 也可手動 /bruno-sync 啟動初次匯入。
---

# Bruno Collection 同步

模式自動判斷：repo 無 `bruno/` → **初次全量匯入**；已有 → **增量同步**。

## 大腦執行流程

1. 偵測框架與路由註冊位置（gin/echo/express…）。**Code 是唯一真相來源**：swagger/openapi 檔只作交叉參考；被註解掉的路由不收。
2. 按大腦規則寫自足 brief 派工人（sonnet、具名、背景），brief 必含下方規則集全文。
3. 驗收（不能只信回報）：
   - 路由數對帳：大腦自己 grep 路由註冊數 vs 工人回報數，**差額必須逐條解釋**（例：註解掉的路由）
   - 跨組抽讀 .bru：method / 完整路徑（含 group 前綴）/ 認證 / body 欄位對 DTO
   - Secrets 掃描：拿 config 檔的實際憑證全文比對 collection，必須零命中
4. Review chain：code-reviewer 必跑；金流專案要求 reviewer 也做 secrets 比對。
5. Git flow：`feature/bruno-*` 分支 → review 過 commit → 地端 `merge --no-ff` 回 dev → **停住不推**。

## 規則集（原文放進工人 brief）

### 位置與結構
- Collection 放 repo 內 `bruno/`，進版控（個別專案另有約定則從其約定）；動工前先驗證 `.gitignore` 不會吞掉 `.bru` / `.md`（負向規則必須排在通配規則之後才生效）。
- 結構：`bruno.json` + `environments/` + 按路由 group 分資料夾 + `MANIFEST.md`（對照總表：METHOD / path / 認證 / handler / 檔案，加「對帳說明」記錄排除了什麼與原因）。
- **分組深度**：角色底下 group 數量多（十幾組以上）時，在角色頂層與 group 資料夾之間加一層「業務大類」中間層（3 層結構：角色 / 業務大類 / route group）；group 數量少的角色維持兩層不動。實體資料夾一律 kebab-case 英文，`folder.bru` 放中文顯示名；業務大類與各 group 的對映表屬於專案決策，落在該專案 `.claude/decisions/` 而非本 skill。auth 繼承仍集中設在角色頂層 `folder.bru`（見下方 Auth 一節），中間層 `folder.bru` 只放 `meta { name }`，不重複設 auth。
- **環境檔只進範本**：`environments/*.bru.example` 進版控，實際 `environments/*.bru` 與 `collection.bru` 加 .gitignore——因為 Bruno App 的 `bru.setEnvVar`（登入 script）與 collection 層 auth 會把**真實 token 寫回檔案**，追蹤實際檔遲早把憑證誤 commit 進 git。MANIFEST 註明「首次使用複製 .example 為同名 .bru」。

### 命名
- `meta.name` 全中文：動詞統一（查詢/新增/更新/刪除/匯出/上傳/登入/登出/重置/結算）；領域名詞從 code 註解與專案 docs 查中文對應；通用縮寫（KYC、GA、FX）保留原文；同資料夾內不重複。
- 資料夾也要中文顯示名：每個分組資料夾（含子資料夾）放 `folder.bru`，`meta { name: 中文名 }`；實體資料夾名維持 kebab-case 英文。
- 登入類 endpoint 的 meta.name 加括號註記自動機制，如「登入（成功後自動存入 token，本組需登入的 API 自動帶入）」。
- **登入置頂**：每個有 token 概念的角色，頂層加 `login/`（中文顯示名「登入」，seq 排最前），收「會簽發該角色 token」的端點；改密碼、登出等非簽發 token 的端點留在原本業務歸屬，不搬進 `login/`。若某登入端點依專案既有歸屬規則本就落在別處（例如與其他公開端點整組歸戶公開分組；判準是歸屬規則本身，不是 `auth: none` — `login/` 內的登入端點通常也是 `auth: none`），**不強行搬動** — 改在該角色頂層 `folder.bru` 的 docs 註明登入端點實際位置（乙案模式），避免同一 API 出現兩處或牴觸其他歸屬規則。`login/` 內端點依 Auth 通則明確設 `auth: none`，不繼承角色 Bearer。增量同步新增的登入類端點固定歸戶 `login/`（見下方增量同步補充）。
- 檔名 kebab-case 英文，不含中文。

### Auth
- 依 token 角色在資料夾層 `folder.bru` 集中設 Bearer auth 與共用 header，request 設 `auth: inherit`；先查證當前 Bruno 版本 folder 設定是否遞迴套用子資料夾，不遞迴就逐層放。
- 不需認證的 endpoint（以實際掛的 middleware 為準）明確 `auth: none`，不得繼承。
- HMAC 簽名類：參數放 body，不走 header auth。
- WebSocket：用 Bruno 原生 WS request 類型，**不得用 HTTP GET 模擬**（語法先查官方文件，查不到就維持現狀並在 docs 註明限制）；scheme 用獨立變數 `wsBaseUrl`（local `ws://`、online `wss://`），不沿用 http 的 baseUrl；認證依 handler 實作（常見 `?token={{變數}}` query param），docs 註明；查得到訂閱協議就附範例訊息。

### 排序（seq）
- request 的 `seq`：照該 group 對應 handler 註冊路由的順序排。
- group 資料夾的順序：照各 group 在路由註冊中首次出現的順序排。
- 業務大類（有中間層時）的順序：照該專案決策文件對映表列出的順序排；`login/` 恆為第一。
- 增量同步新增端點：依其在路由註冊中的位置插入對應 seq，不得一律排到最後。

### Token 自動帶入
- 登入類 endpoint 加 `script:post-response`：成功時 `bru.setEnvVar` 存進**對應角色**的變數（前台/後台/商戶分開、互不覆蓋）；token 取值路徑**以 handler 實際 rep.Success 的內容為準**（DTO 定義可能與實作不一致，曾實測過 data 直接是 JWT 字串而非 DTO 物件），不准猜、也不得沿用其他角色已驗證過的路徑（每個角色各自實測）；失敗或欄位不存在不覆寫既有值。
- 一次性憑證（resetApiKeys 類，僅回傳一次的 secret）同樣加 script 自動存。
- **自動登入腳本**：有 token 概念的角色，頂層 `folder.bru` 加 `script:pre-request`：該角色 token 為空時，用 environment 對應的帳密自動打該角色登入 API，成功即 `bru.setEnvVar` 存 token 後再送出原請求；用 `bru.sendRequest`（axios 語義，回應體在 `res.data`）呼叫登入 API，**不用 `bru.runRequest`**（在 folder script 內呼叫會遞迴觸發自身）。注意 `bru.sendRequest` 是裸請求、**不吃 folder headers 繼承**：登入 API 若要求共用 header（裝置指紋、CSRF 類），腳本內必須明帶（實測漏帶時後端回「請求無效」類錯誤、難察覺——手動跑登入因繼承會過，只有腳本打的會失敗）。腳本須以 URL 比對豁免「登入請求本身」不觸發自動登入（避免手動送登入時多打一次；漏豁免僅造成無害的重複登入）。
- 同一 `folder.bru` 加 `script:post-response`：偵測到 HTTP 401 或該專案定義的「業務未授權」code 時，清空該角色 token 並自動重登；Bruno 無原生自動重送原請求的機制，docs 註明「重登後需手動重新送出該請求」。
- 需二階段驗證（GA / TOTP 等）的角色：判斷到相關 code 時**不覆寫既有 token**、也不嘗試自動完成二階段流程，docs 註明需手動走登入補驗證。
- environments 增對應 `roleUsername` / `rolePassword` 變數（依角色命名，如 `adminUsername`/`adminPassword`），只進 `.example` 範本、值留空；local/online 環境結構維持完全相同。
- docs 須註明：「帳密錯誤沒有失敗記憶（每次都會重試登入），連續觸發可能造成該角色登入鎖定」。

### 範例完整性（硬性驗收）
- POST/PUT body 逐欄對 req DTO，值要合理；GET query 對 form tag / `c.Query`；路徑參數（`:id`）給範例值。
- 工人須交自查清單：掃描 handler 所有參數綁定 vs .bru 範例，「有綁定無範例」數量必須為 0，例外（multipart 上傳等）逐條列原因。

### 基本 assert 政策
- 每支 request 一律加 `res.status: eq 200` + `res.body.code: eq <該專案統一封包的成功 code>`（成功 code 從專案的統一回應封裝，如 `rep.Success`，查證取得）。
- 不驗 `res.body.data`：統一封包的 data 欄位常見 omitempty，逐支硬驗存在會誤報。
- 例外（逐條記進該專案 `MANIFEST.md`，不得省略）：
  - WebSocket request 不加狀態碼/body assert（走原生 WS，無此概念）。
  - 檔案下載類 request 只驗 `res.status: eq 200`，不驗 body。
  - 不走統一封包的 handler：逐支依實際回應格式個別處理 assert。
  - 登入類 endpoint：留意該專案的二階段驗證（GA 等）流程可能回傳「業務未授權」但屬預期流程的 code，逐支確認該 code 是否真的代表失敗，避免誤紅。
- 目的：Bruno App 內紅綠燈即時判讀請求是否成功，並讓 `bru run` CLI 之後可跑整包回歸；是否接 CI 留待 assert 實際使用一段時間後再議。
- 此政策同時適用初次匯入與增量同步；增量同步新增/修改的 request 一併補齊 assert（見下方增量同步補充，assert 不屬「使用者手動維護內容」的保護範圍）。

### 環境與安全
- `local.bru` 與 `online.bru` 變數結構完全相同（驗收逐欄比對）；online 域名從 config / nginx / deploy 腳本查證實際網址並附出處，須確認是 **API** 域名而非前端頁面域名；查不到就回報、不准亂填。
- 各角色 API 走不同域名時，baseUrl 依角色拆分（userBaseUrl / adminBaseUrl / agentBaseUrl…），local 全指向同一 localhost 也要分開定義，各分組 request 用對應變數；public / system 類分組的歸屬從 nginx 路由查證；WS 變數同理依角色拆。工人須交「分組 → 變數 → online 域名 → 出處」對映表。
- 所有 token / key / secret 變數一律留空；任何實際憑證禁止出現在任何檔案。

## 增量同步模式補充

- 範圍：本次 git diff 涉及的 route / handler / DTO。
- 先讀既有 `.bru` 再合併更新，不整檔重寫；**不得動使用者手動維護的內容**（tests、自寫 docs、範例調整）。assert 不在保護範圍：由同步政策統一管理（見上方「基本 assert 政策」，Mike 定案 2026-07-22）。
- 新端點的歸戶與排序：登入類端點固定歸 `login/`（見上方「登入置頂」）；其餘依既有分組規則歸戶；新端點 seq 依其在路由註冊中的位置插入（見上方「排序（seq）」），不得一律排到尾端。
- 被刪除的 endpoint：移除對應 `.bru` 並在回報中列出。
- 回報格式：新增 / 修改 / 刪除的 endpoint 清單。
