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

- `vue-tsc --noEmit`（或該專案 build script 已內含 vue-tsc 的 `pnpm build` / `npm run build`）**實際輸出**
- 專案有 lint script 就跑 lint，附實際輸出
- brief 的驗收標準必須把上述寫成可執行指令；工人回報未附實際輸出視同未完成

## 瀏覽器實測（Chrome DevTools MCP，2026-08-07 起）

取代測試檔的行為驗證層，/quick 與 /feature 驗收都適用：

1. 起該專案 dev server（背景跑，用專案既有 script）。
2. 用 Chrome DevTools MCP 開啟受影響頁面，**實際走一遍操作流程**（點擊、填表、送出）。
3. 驗收證據三件：**截圖**（改動前後的畫面）、**console 無新增錯誤**、**network 面板該打的 API 有打且回應正常**。
4. brief 的驗收標準要把「走哪些頁面、做哪些操作、預期看到什麼」寫成具體步驟；bug 修復時把重現步驟固化成可重走的驗證步驟（等同回歸測試）。
5. 地端連 online 測試的專案（該專案 CLAUDE.md 的完工流程有標注）沿用既有連線方式，完工後起地端 dev 給 Mike 實測。
6. **review chain 複驗**（/feature 適用）：大腦驗收後，ui-reviewer agent 拿 brief 同一份實測步驟用 Chrome DevTools MCP 再走一遍（只測不改），三件證據同上；大腦親測與 ui-reviewer 複驗是兩道獨立防線，不可互相替代。

## Package manager

lock 檔是什麼就用什麼（`pnpm-lock.yaml` → pnpm，禁止混用產生第二份 lock 檔）；新專案一律 pnpm。
