---
name: feature
description: 標準工程 lane：範圍明確、超出 /quick、技術路線清楚的新功能或修改。brief 派工、驗收、review chain 的完整流程在此。
---

# /feature — 新功能 / 修改

## 入選標準

- 範圍明確、超出 /quick（>3 檔案、行為變更不小、或命中 /quick 硬排除）
- 技術路線清楚，不需要先解決策（需要探路 → /mega）

## 流程

### 1. 需求對齊

- 符合任一：`跨服務`、`涉及金流`、`不可逆操作`、`全域配置`、`範圍明顯大於直覺` → 先提 **A/B 兩方案**（各含取捨與風險）給 Mike 選，等點頭才動工。
- 新專案 / 新需求第一次動工前：與 Mike 討論需求與寫法，結論落檔專案 `CLAUDE.md`；重大決策依三條件（難回頭、不看脈絡會奇怪、真有取捨）補 ADR（新專案 `docs/adr/` Matt 格式；有 `.claude/decisions/` 的舊專案沿用原路徑與四段格式）。
- 已有共識 → 明講「共識已存在（出處），跳過討論」直接動工。

### 2. 拆任務 ＋ 派工

- 每個子任務用 /brief 八欄模板寫自足 brief；seam 沒議定不派工。
- 分支與 worktree 一律走 /feature-flow（先 /sync-dev）。
- 具名工人 `run_in_background: true` 平行派工；命名、單波上限、模型選配依全域不變式。

### 3. 驗收（done ≠ done）

1. `git log` 確認 commit 存在
2. `git diff --stat` 確認範圍與 brief 相符
3. 抽讀關鍵檔案
4. **親自跑可執行證據**：相關測試 ＋ typecheck/build 至少一項；工人未附實際輸出視同未完成
5. 不符 → 重寫 brief 重派，並記退件（見下）

### 4. Review chain（驗收通過後）

| Reviewer | 觸發 |
|----------|------|
| code-reviewer | 每次都跑 |
| security-reviewer | 金流/付款/認證授權/secrets |
| db-reviewer | DB schema / migration |

- 有問題 → 退回重派，修完**重跑 review chain**；退件記錄依全域退件回饋迴路。

### 5. 收尾

合併依 /feature-flow 階段三、四；commit 後停下。

## 領域插件

- Go：brief 紀律欄引 /tdd；驗收證據 `go test` ＋ `go build`；碰 schema 觸發 db-reviewer。
- Vue：brief 紀律欄引 /vue-dev、/vue-ui-patterns；驗收證據 `vue-tsc --noEmit` ＋ **Chrome DevTools MCP 瀏覽器實測**（不寫測試檔，詳見 /vue-dev）。

## 跳線

- 途中冒出未決技術選型 → 宣告升級 /mega（先解決策再回來拆工）。
- 發現根因不明的壞行為 → 宣告轉 /bug。
- 發現其實極簡單 → **先問 Mike** 才降 /quick（降級不得自主）。
- 要中途暫停 / 交接 → /wip 收斂。

## 回報格式（五點）

1. 改了什麼 2. 為什麼 3. 影響面 4. 驗證證據（測試輸出、diff stat）5. 還可以做什麼（不擅自執行）。
答案先行、次要問題只在第 5 點列一行、多波任務帶進度重述（N 波完成 M）。

**影響面（第 3 點）的紀律**：寫「改 A 會導致 B」之前把 B 那段程式碼讀到底（守衛條件、early return、迴圈取的是哪一層）——grep 到欄位被讀只證明被讀，不證明在哪個分支對誰生效；先搜同專案有沒有人論證過同一件事；「完全相同／不變」要帶值域條件；影響面宣稱在 brief 裡標成待驗假設交 reviewer 查證。錯的影響面會寫進 commit message 變成下一個人的錯誤前提。
