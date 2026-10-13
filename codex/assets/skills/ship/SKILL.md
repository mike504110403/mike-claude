---
name: ship
description: 在 Mike 明確授權後推送已驗收的本地成果並核實 remote hash。
---

# ship

先盤點 branch、remote、待推 commits、驗收/review、ledger 和未保存工作。未經 Mike 明確說推不可 git push；推 repo 主幹前明確問，附建議、理由與推/不推後果。任務授權與 sandbox 權限分開判斷，hooks 不能合成人類批准。授權後普通 push 精確 branch（禁止 force），再 git ls-remote 比對本地 commit hash，只有一致才宣稱成功。保留失敗證據；不同 remote/branch 不繼承授權。
