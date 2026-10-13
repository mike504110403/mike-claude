---
name: code-review
description: Review 固定 base 以來的分支或未提交改動，分別審查 Standards 與 Spec。
---

# 兩軸 Review

先確認使用者的範圍：branch commits、staged、unstaged或全部WIP。固定 base 並 `git rev-parse`解析為hash；分支用merge-base後記實際hash，不讓移動ref改變review內容。記HEAD、diff命令、commit摘要與檔案清單；WIP需包括指定的index/worktree及untracked檔，不用只有三點diff漏掉它們。bad ref或空diff先說明。

Spec從使用者提供的brief/issue/PRD、commit引用或repo文件查找；外部issue使用當前可用且已授權connector，不假定issue-tracker安裝。缺spec不捏造，先做Standards並將Spec標未驗／無spec。

Standards讀適用AGENTS、CONTRIBUTING、code conventions和相關ADR；repo約定優先。命名含糊、重複、Feature Envy、Data Clumps、Primitive Obsession、重複switch、Shotgun Surgery、Divergent Change、Speculative Generality、Message Chains、Middle Man、Refused Bequest只是判斷啟發，必須指出具體維護／行為代價，不能把喜好當必修。

有原生subagent或review介面可用時，並行派唯讀Standards與Spec reviewer；各brief自足，帶固定base/HEAD、選定diff範圍、文件路徑與預期輸出。角色沿用父runtime模型，不填虛構模型／工具。不具備並行能力就依序審查兩軸並明示。review期間若diff變了重新固定範圍，不能沿用舊結論。

每個finding附severity、精確檔案:行號、規則／需求引用、觸發情境、影響和最小建議。Spec列缺失／部分實作／錯誤實作／未要求行為；Standards區分硬違規與建議。不修改檔案、不自動跑不獲授權的tests、發PR comment或外送code。

回報兩軸各自finding數與最重問題，不讓一軸通過掩蓋另一軸；標明未驗、spec缺失與scope限制。Review不是runtime證據。
