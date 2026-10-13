---
name: feature-flow
description: 管理已核實主幹、需求與實作者 worktrees、串行整合、重驗及保存。
---

# feature-flow

## 開工與路由

先核實 repo AGENTS、已存在 worktrees、status 與基底；代號/跨裝置路由按 [references/PROJECT-ROUTING.md](references/PROJECT-ROUTING.md)，不假設全域 registry 存在。載入 /sync-dev，確認 repo 記錄的主幹與 remote，fetch 後只 ff-only；來源 dirty 與本地 ahead commit 保留，若阻擋同步先回報，不能自動 stash/reset。記開工 base hash與驗證基線。

App 優先重用合適 managed worktree，新增時明確 ref，在返回的絕對 cwd 工作；detached HEAD 合法，記實際 HEAD hash，不編造 branch。工具以本回合可用為準，不 self handoff。CLI fallback 用 git -C 的具名 feature branch/worktree，主 checkout 維持 repo 主幹，不改來源 dirty 檔。

## 並行與整合

單一實作者可在 feature worktree；所有同時實作者各用獨立 worktree，branch/cwd/HEAD 寫進 brief。共享元件及 consumers 同 ownership。改他人 in-flight 檔先 native 協調或中止；不共用 index 夾帶 staged 檔。worker 只在 brief 授權時提交，其他 Git 整合由主控串行做。

逐片 verify/review 通過再整合，不用分支回報代替實際 diff。重寫/整併只操作本需求尚未發布且乾淨的 commit；先保存實際 HEAD 與內容，detached HEAD 需先有可恢復 ref/快照才清理。一需求主幹保持一顆整合 commit，標題 type:一句話，必要 body 只記 why/風險/裁示。

基底前進先把最新主幹整合到 feature 並重驗對應改動面；只有成功才串行整合回主幹，再以主幹結果核對並重驗。失敗保留 feature/worker worktrees與證據，停止清理；主幹失敗處置先確認影響與授權，不自動破壞他人 commit。

## 保存與清理

暫停/續作按 /wip：不 merge/push/delete。完成後先保存未結裁示、accepted risks 到既有 ADR（無則 docs/adr），再只清本需求自行建立且已保存的產物。App archive_worktree 依實際工具保存快照；CLI 正常 remove 精確 worktree、branch -d，先親看 status，禁止 force。共享 worktree、別人檔、memory 或廣泛索引都不清。

驗收/review 後本地 commit；push 另走 /ship。App 用原生進度與 commentary，CLI 可用 /statusline 的原生 item IDs；不依賴任意 stdin/stdout statusline dispatcher 或不存在的 phase helper。
