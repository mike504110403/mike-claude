---
name: vue-dev
description: Vue 前端專案的開發不變式（強制 script setup + TS、只用 Pinia、走既有 axios 封裝、i18n、typecheck 驗收證據）。任何 Vue 專案的工程任務，brief 紀律欄一律引用本 skill。
---

# /vue-dev — Vue 專案開發不變式

適用所有 Vue 專案。本 skill 只收斂**跨專案一致的不變式**；分歧項（UI 框架、目錄結構、API 封裝位置、env 命名、遺留豁免）一律**跟隨該專案 CLAUDE.md**，沒有 CLAUDE.md 就跟隨該專案既有程式碼慣例，看不出慣例就停下問，不自行發明。

## 不變式

1. **元件一律 `<script setup lang="ts">`，禁 Options API。**（遺留專案的豁免寫在該專案 CLAUDE.md——有豁免宣告的只修不改寫。）
2. **狀態管理只用 Pinia。** Pinia/Vuex 並存的遺留專案（各自 CLAUDE.md 有標注）新 store 一律 Pinia，**禁止新增任何 Vuex 用法**（不加 module、不加 dispatch 呼叫）。
3. **API 呼叫一律走該專案既有的 axios 封裝**（`services/axios.ts` 或 `api/request.ts` 派系，看專案）；禁止元件內裸 `import axios`、禁止另起第二套封裝。token 與錯誤已由攔截器統一處理，不在元件層重複做。
4. **元件檔 PascalCase**；其他命名跟隨該專案慣例（專案 CLAUDE.md 或既有程式碼）。
5. **有 `locales/` / `lang/` / `languages/` 的專案，禁止硬編碼使用者可見字串**，一律走 i18n。
6. **UI 框架用該專案既定的那一套**（Element-Plus / Vuetify / Quasar），禁止引入第二套或混用元件庫。
7. **樣式跟隨所改檔案的既有寫法**（多數專案 SCSS；並存 Tailwind 的專案見其 CLAUDE.md），不跨檔搬風格。
8. **loading / 錯誤處理 / 資料獲取**遵循全域 `/vue-ui-patterns`；專案級的表單／元件模式 skill（如 `/vue-form-patterns`）在該專案內自動載入，照隨。

## 驗收最低證據

Vue 專案不寫測試檔（Mike 裁示），防線 = typecheck ＋ 瀏覽器實測兩層：

- `pnpm exec vue-tsc --noEmit`（或該專案 build script 已內含 vue-tsc 的 `pnpm build`）**實際輸出**；一律用專案自身執行檔，**禁止裸 `npx`**——無 node_modules 時 npx 會靜默從 registry 抓新版，產出假結果
- lint 是驗收標準不是 hook 的事（2026-08-12、08-13 兩犯定案）：brief 驗收標準必含「eslint／stylelint **0 新增 error**（附實際輸出）」；**不得假設 pre-commit hook 會代跑**——已實測兩 repo 的 hook 一個被移除、一個被繞過。lint 工具本身壞掉（如 eslint.config 與版本不相容）→ 回報列為順路發現並在回報明寫「lint 無法執行」，不算通過
- brief 的驗收標準必須把上述寫成可執行指令；工人回報未附實際輸出視同未完成

## 瀏覽器實測（行為驗證層，2026-08-20 改版）

取代測試檔的行為驗證層，/quick 與 /feature 驗收都適用。**行為驗證主防線＝Mike 地端手測**（review chain 手測並行站，見 /review-chain）；/auto-e2e（Playwright 腳本實測）與 ui-reviewer 僅 on-demand：

0. **環境前提**：需要真後端的頁面（登入、取資料、送出寫入）先用 `/local-stack` 起地端全棧；環境不可得時走該 skill 的降級階梯，並在 wip.md 記一筆驗證債。**不要拿 dev server 預設的 API 位址就開測——多個專案的 `.env` 預設指向正式線上**，在上面按下「送出」是真的在改線上資料。
1. 起該專案 dev server（背景跑，用專案既有 script），**明確覆蓋 API 位址指向地端**。指向判準＝**經 proxy 的請求得到只有地端才可能的回應**（seed 帳密登入成功、地端獨有資料），頁面 200 什麼都不證明；Vite env 分層（`.env` → `.env.[mode]` → process env）全部查完才能宣告預設值。
2. brief 的驗收標準要把「走哪些頁面、做哪些操作、預期看到什麼」寫成具體步驟；bug 修復時把重現步驟固化成可重走的驗證步驟（等同回歸測試）。**這份清單就是 Mike 手測站的重點路徑清單**（on-demand 代測也共用同一份）。
3. **on-demand 自動化實測證據**（/auto-e2e，Playwright 腳本）：exit code＋trace＋失敗截圖；console 無新增錯誤與「該打的 API 有打且回應正常」寫成 spec 內斷言。互動式診斷（/bug）改用 playwright-cli 具名 session（`-s=<名字>`，互不互踩）；chrome-devtools MCP 僅剩效能診斷（trace／lighthouse／heap），動用時同時僅 1（共用選頁指標，`isolatedContext` 擋不住互踩）。
4. 地端連 online 測試的專案（該專案 CLAUDE.md 的完工流程有標注）沿用既有連線方式，完工後起地端 dev 給 Mike 實測。

## Package manager

lock 檔是什麼就用什麼（`pnpm-lock.yaml` → pnpm，禁止混用產生第二份 lock 檔）；新專案一律 pnpm。
