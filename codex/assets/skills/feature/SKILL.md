---
name: feature
description: 執行範圍明確且需獨立切片派工、跨 repo 或專門審查的工程變更。
---

# feature

## 定邊界

先確認需求、repo 與技術路線；未知選型升 /mega，未知故障轉 /bug。交付 ≤5 行邊界卡：目標／改動面（repo×層）／非目標（相關 ledger 雷）／影響面（已驗證據或明列待驗）／待裁示。跨服務、金流、不可逆操作、全域配置或範圍明顯大於直覺且尚無已授權共識時，附 A/B 方案、各自後果與建議，等 Mike 選定才做依賴工作。已有共識則引用出處、明示邊界鎖定並直接進行；不得重問同一裁決。超出卡面需重新對齊。

新專案或重大決策記 repo AGENTS 或沿用 docs/adr；難回頭、有真實取捨或缺脈絡難懂的決定持久留 ADR。裁示攢批，只有阻塞關鍵路徑才即時問；可逆純 UI 呈現取捨已預授權，可先做並回報。

## 拆分與派工

按 /feature-flow 同步已核實主幹並建 worktree。只有獨立切片才派 native subagents；共享元件與其全部消費者由同一 ownership 負責，無法獨立時不硬拆。小範圍單次搜尋可回答的問題主代理直讀；跨模組問題用 explorer，圖存在時先 /graft。

派工前載入 /brief 的 BRAIN-CHECKLIST.md，寫八欄自足 brief，親驗當下環境與引用 facts。所有同時實作者使用獨立 worktree，禁止覆蓋他人 edits；附 cwd、branch/base、log 路徑與提交授權。角色沿用父模型，核對有效 sandbox 和 runtime 額度。

工人與 brief-reviewer 影子並行審同一份 brief，不設串行 approval gate；影子只有 BLOCKER 才中止依賴工作、修 brief 後續作，MAJOR/MINOR 攢至驗收處理。額度不足或原生 API 不可用時明示 fallback：主代理立即獨立核對 brief，記缺少影子限制。背景連續無落地證據時先查 cwd、日誌、實際工具狀態，不反覆盲派。

## 驗收到收尾

工人完成一片即 /verify，主代理可同時接其他獨立回報。/review-chain 依 diff+spec 審；前端 Mike 手測與 review 並行且兩者皆過。修復提供全體指派清單與實跑證據，重審規則依 /review-chain。整合只由主控串行操作，基底前進後依 /feature-flow 重驗，失敗保留 worktree。

API 改動且既有 bruno/ 才自動 /bruno-sync 增量同步；沒有不初次匯入。驗收/review 通過才 commit，push 另走 /ship。收尾遵守全域 AGENTS.md「工程收尾」五點與四項實際狀態，該節是格式唯一 source。
