---
name: verify
description: 主代理對照實際 diff/spec 親驗，按改動面與已授權 checks 產出可執行證據。
---

# verify

/mvp 專案不適用本技能：驗收與畢業總審以 /mvp 為準。

1. 先對照看板/brief 的需求、worktree、base/HEAD；親看 diff --stat 與關鍵內容，若尚未 commit 就明示工作樹驗收，已 commit 才用 commit diff，不能拿兩者混稱。
2. 範圍對帳含 producer/consumer 與所有修正項；接手既有保證作待驗清單，工人聲稱不是完成證據。Commands/已知基線按 /feature-flow 的路由資源核實，基線紅只決定歸屬，不等於豁免。
3. 親跑適用且已授權 checks，逐一讀實際輸出而非只看 exit；沒有工具/依賴/授權就記未驗，不能聲稱成功。後端：適用 tests+build；前端：typecheck、地端 API、Mike 手測；Vue 引 /vue-dev，環境引 /local-stack，瀏覽器選擇引 /browser-tools。全域工作流或腳本依其 validate/fixtures；不為可逆文案新增鏡像 tests。
4. 修復相關守衛有已授權測試時，重大變異可依 [references/MANUAL-MUTATION.md](references/MANUAL-MUTATION.md) 手工證明；不依賴未部署 helper，也不拿變異證明 oracle 正確。

地端不足依全棧→只起後端→靜讀/跨端對照降階，每降一步記 .codex/wip.md 原因、替代證據、未驗項及補驗腳本。先核實前端 API 地址；不要按預設正式 API 送資料。自動瀏覽器測試只在明確授權時 /auto-e2e。

前端 Mike 手測與 review 並行，提供地端入口/操作/預期；兩者皆過才整合，Mike 未測就保留待驗，不以自動測替代未授權的判定。MAJOR/BLOCKER 前端修正重測受影響路徑，其他按 /review-chain。

API 改動且已有 bruno/ 才自動 /bruno-sync 增量同步，再對合約驗收；沒有 bruno/ 不自動初次匯入。通過後 /feature、/solo 進 /review-chain；/quick 按已核實風險裁剪。整合基底前進則依 /feature-flow 重驗。
