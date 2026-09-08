---
name: feature-flow
description: 工程的分支與 worktree 生命週期：主 checkout 恆 dev，每個需求一個 feature worktree、每個工人一個 wt/ worktree；合併回 feature 即清工人 worktree，合併回 dev（含重驗＋三清）即清 feature。所有 lane（含 quick/solo 直改）與同 repo 多需求並行都走這個拓撲。
---

# /feature-flow — 分支 / worktree 生命週期

## 拓撲不變式（2026-08-12 起）

- **主 checkout 永遠站 dev**：只做 /sync-dev 與階段四合併，HEAD 不切換、不直接改 code。
- **每個需求一個 feature worktree**（quick/solo 直改也在裡面做）；**同一波有 ≥2 個 implementer 時，每個工人一個 wt/ worktree** 從 feature 掛出；**一波只有一個 implementer → 直接在 feature worktree 工作，不開 wt/**（2026-09-07 起，省一層 worktree add／trust／裝依賴／合併／清理；與 dev 的隔離不變）。任何 checkout 的 HEAD 從開到收都不變——`git -C` 打錯路徑時，HEAD 也不會是意料外的分支。
- 同 repo 多需求並行＝多個 feature worktree 並存；**合併回 dev 一律由大腦串行執行**；每 repo 同時至多一個大腦 session（全域不變式）。
- 派 Agent 不帶 `isolation: "worktree"`——worktree 由本 skill 手動開、手動收，生命週期才可控。

## 階段一：開需求

1. 先跑 /sync-dev 把 dev 拉到最新。
2. `git worktree add ../<repo名>-feature-<需求slug> -b feature/<需求slug> dev`
   - 接著 `~/.claude/bin/trust-dir ../<repo名>-feature-<需求slug>`（claude 2.1.258 起 trust 走訪到 git root 即停，每個 worktree 都要各自信任，否則在裡面開的 claude／teammate 會卡在 trust dialog）。
   - 主 checkout 有 `graft/.graph/wiring.json` 的 repo（2026-09-08 起）：在新 worktree 內 `graft build --lsp --no-gitignore --no-ignore .`（cache 共用、秒級）——`graft/` 是 per-directory 產物，worktree 不會繼承；階段二的 wt/ worktree 同樣各建一次。
3. 在 /wip 看板記一行（多需求並行時必開）：需求、feature 分支、**切自 dev hash**（`git -C <主checkout> rev-parse dev`）。
4. feature 分支不推 remote（全域規則）。前端專案順手依 lock 檔裝依賴（如 `pnpm install --frozen-lockfile`）並確認 `node_modules/.bin/` 有驗證工具（/brief 的 VERIFICATION-TRAPS #6）。

## 階段二：每個工人開一個 worktree（派工前；**單工人波次整段跳過**）

**單工人**：不開 wt/，brief「工作環境」欄直接寫 feature worktree 絕對路徑與 `feature/<需求slug>` 分支（其餘限制同下：不 merge／不 push／不切分支／不動 worktree 外目錄）；階段一已跑過 trust-dir 與裝依賴。**後來又要加派第二個工人** → 第二個起才開 wt/，第一個留在 feature worktree 不搬。

**多工人**：

```
git worktree add ../<repo名>-wt-<task-slug> -b wt/<需求slug>/<task-slug> feature/<需求slug>
```

- 開完立刻 `~/.claude/bin/trust-dir ../<repo名>-wt-<task-slug>`，再派工——沒信任的 worktree，teammate pane 會停在 trust dialog，外觀就是「工人未動工即死」（零 commit、inbox 未讀）。
- worktree 放 repo 外側 sibling 目錄，不污染 repo；前端專案同樣先裝依賴再派工。
- brief 的「工作環境」欄必寫：worktree 絕對路徑、`wt/<需求slug>/<task-slug>` 分支、commit 全留在此分支、不 merge / 不 push / 不切分支 / 不動 worktree 之外的目錄。

## 階段三：整併 commit ＋ 合併回 feature ＋ 清工人 worktree（單一工人驗收＋review 通過即做，不等整波；**單工人波次跳過，commit 整併留到階段四第 1 步**）

1. **整併 commit——一任務一顆**。在工人 worktree：
   ```
   git -C <工人worktree> reset --soft $(git -C <工人worktree> merge-base HEAD feature/<需求slug>)
   git -C <工人worktree> commit -m "<type>: <任務描述>"
   ```
   - 過程 commit 全部壓成一顆，message 一行從簡即可（階段四整需求壓縮時會重寫）；本來就一顆則跳過。
   - reset --soft 前先 `git -C <工人worktree> status` 確認沒有未 commit 改動混入。
2. **在 feature worktree（不是主 checkout）合併**：先 `git -C <feature worktree> branch --show-current` 確認站在 feature 分支 → `git -C <feature worktree> merge wt/<需求slug>/<task-slug>`。
   - 衝突依 /resolving-merge-conflicts 逐塊解；解不掉回報 Mike。
3. 合併成功後**立即清工人 worktree**，三步一組：`worktree remove` → `branch -d` → `worktree prune`。被擋不 force——先查明未 commit 改動或未合併 commit 是什麼再處置。

## 階段四：壓成一顆 ＋ 合併回 dev ＋ 重驗 ＋ 三清（需求全部驗收＋review 通過後）

1. **需求壓成一顆**（**一個 /feature 落 dev 恆一顆 commit**，2026-08-20 定則）：先 `git -C <feature worktree> status` 確認無未 commit 改動 → `git -C <feature worktree> reset --soft $(git -C <feature worktree> merge-base HEAD dev)` → `git commit`，訊息依下方精簡規則。
2. dev 自本需求切出以來**前進過**（比對看板「切自 dev hash」）→ `git -C <feature worktree> rebase dev`（衝突依 /resolving-merge-conflicts；feature 未推 remote，rebase 安全）；沒前進 → 跳過。
3. 在主 checkout：`git -C <主checkout> branch --show-current` 確認是 dev → `git merge feature/<需求slug>`（此時必為 fast-forward；出現 merge commit 代表前兩步沒做對，停下查）。
4. **合併後重驗**（merge queue 的後半）：dev 前進過的需求 → 在主 checkout 就地重跑本需求改動面的驗收證據（指令同 /verify 第 4 步）。
   - 失敗 → **不刪 feature 分支**，`git revert <該顆 commit>` 或掛待修回報；dev 未 push，可安全回退。
   - dev 沒前進過（單需求串行）→ 本步零成本跳過。
   - **graft 圖重建**（2026-09-08 起，主 checkout 有 `graft/` 才做）：合併後主 checkout 的圖已過期，重驗前先 `graft build --lsp --no-gitignore --no-ignore .`；大腦 session 的 hook 不會碰主 checkout，這裡是唯一更新點。
5. 通過 → `git branch -d feature/<需求slug>` ＋ 清 feature worktree（三步同上）。
6. **map delta 更新**（該 repo 在 `~/.claude/maps/` 有 map 才做）：本需求觸及的 map 條目逐條校正（function 改名/搬家/消費者增減），該區塊「最後核對」戳更新為今日＋dev 新 hash；沒觸及任何 map 條目則跳過。
7. **三清**（工程死亡點）：`~/.claude/bin/phase clear`、刪本工程 wip.md（未結裁示與已接受風險先搬 ADR 或 repo CLAUDE.md，否則隨檔死亡）、刪本案 memory 檔及 MEMORY.md 索引行（若有）、刪本需求 e2e spec 目錄（`~/.claude/e2e/specs/<repo>-<需求slug>/`，若有）。
8. 停下。push 走 **/ship**。

### Commit 訊息精簡規則（dev 上那顆）

- 標題一行 `<type>: <一句話>`，講清楚做了什麼就停——不寫條列清單，改了哪些檔 diff 自己會說。
- body 至多三行，只寫 diff 看不出來的事（why、風險、Mike 的裁示）；沒有就不寫 body。
- **不帶任何尾綴**（無 Co-Authored-By、無 Claude-Session——settings.json attribution 已全域關閉，Mike 2026-08-20 裁示）。

## 與工人共處（多方同 repo 紀律）

- **派工前先看該 repo 有沒有未收工的工人**，不是數「這一波派幾個」——前一個沒收工就派下一個同樣是並行，同檔改動會互踩。
- **大腦要動工人 in-flight worktree 的檔案**：先 SendMessage 宣告「我將動 X」再動手，或等工人 idle——工人視角「檔案憑空消失」會弄壞 build 並動搖它對工作區狀態的信任前提。
- **多方共用 index 時，裸 `git commit` 是夾帶機**：大腦在工人 worktree staged 過東西後，工人一律 `git commit -- <pathspec>` 部分提交；大腦驗收用 `git show --name-status` 對 commit 訊息聲稱的範圍勾稽。
- **SendMessage 只進 inbox，長回合工人整場讀不到**（實測：工人自開工到 TaskStop 全程未讀任何一則，同時還在主動發訊息——送與收是兩條路）：中途裁示後工人行為不符，第一假設是沒收到不是抗命；急停不等回應，直接 TaskStop＋大腦親自收斂。契約類內容一律派工當下寫進 brief。
- **繼承來的未完成工作，第一次驗收通過就先 commit 當基準點**，不等整批做完——否則跨輪複審隔離不出當輪改動，工人只能自報 Edit 內容當證據。

## 異常路徑

- 暫停／交接 → /wip 收斂：**不做任何清理**，worktree 與分支原樣保留給續作。
- 工人被退件 → 重派沿用同一 worktree；任務作廢才走階段三清理（先確認分支內容確定不要）。

## 禁止事項

- 大腦所有 git 操作一律 `git -C <絕對路徑>` 顯式指路徑；破壞性指令（reset/merge/branch）前先 `git branch --show-current` 確認該 checkout 的 HEAD 是預期分支。
- 主 checkout 不切分支、不直接改 code；一切改動發生在 worktree。
- **清 worktree 前先 `git status`**：工人回報「乾淨」不一定準（實測遇過工人改完更好的版本沒 commit 就回報）。
- 不 push 任何分支（push 只發生在 /ship）。清理只用 `-d` / `remove`，絕不 `-D` / `--force`（hook 硬擋）。
