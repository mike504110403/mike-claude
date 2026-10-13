---
name: vue-dev
description: Vue 工程遵循 script setup TS、Pinia、既有 axios／i18n 與 typecheck／地端手測規則。
---

# Vue 開發

先讀AGENTS與現有約定，legacy例外只在明確記載範圍內維持，不借例外新增舊模式。新元件用 `<script setup lang="ts">`，PascalCase檔名；新store只用Pinia，不增Vuex module/dispatch。API統一走專案已有axios封裝，組件不裸import axios、不建第二套client或重復token/error interceptor。

專案有locales/lang/languages時，用戶可見字串一律i18n；UI framework、style和目錄沿已有約定，不引第二套。loading/error/data fetching依vue-ui-patterns，專案獨有模式僅在存在且適用時讀。

Package manager由packageManager與lock決定，不硬套pnpm或混造lock。typecheck用專案已安裝local binary與script；pnpm專案可用已存在的vue-tsc經`pnpm exec vue-tsc --noEmit`，build含typecheck就覈實後用build。禁止裸npx靜默下載；缺node_modules／binary回報缺項。

Mike的Vue專案不新增test文件；驗收用typecheck與地端手測。按本次授權執行eslint/stylelint並相對base判0新增error，不假定hook會執行。工具配置壞掉記未驗／ledger，不算通過。

需要真實API時local-stack先就緒，檢查Vite env優先序、mode、process env與proxy，顯式覆蓋到local，並取得request返回地端獨有響應的證據；頁面200不算API指地端。預設.env可能連正式線，未覈實不得送出寫入。

整理Mike手測路徑：頁面、操作、預期畫面與關鍵API。實際手測需Mike結果，不能把開URL稱通過；on-demand auto-e2e才產spec實跑。無法起棧依降級階梯在wip記驗證債。回報typecheck/lint證據、手測狀態、API address proof與未驗限制。
