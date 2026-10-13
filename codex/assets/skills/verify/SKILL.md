---
name: verify
description: 主代理驗收實際改動，以需求、diff 與風險選取可執行證據。
---

# verify

先讀實際 diff 與 originating spec，確認完成的是同一件事。親跑改動相關 checks，不憑工人聲稱。後端：適用測試+build；前端：typecheck+地端 API+Mike 手測，自動瀏覽器測試須明確授權。先核實 API 地址，缺地端依序降至後端、靜讀對照，每次記 .codex/wip.md 驗證債（原因、替代證據、未驗項、補驗命令）。腳本/全域工作流：fixture 驗收及 build/validate。全部通過後才交 review-chain，風險或新失敗才擴大/重測。
