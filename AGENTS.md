# mike-claude 工作流來源專案

本 repository 同時版控 Claude 與 Codex 工作流。`CLAUDE.md`、根 `skills/`、`agents/`、`hooks/`、`bin/` 是 Claude 來源；`windows/` 是 Windows 的 Claude 版本；`codex/` 是 Codex 原生版本。

## 修改與版控

- 本 repo 的主幹是 `main`。需求在隔離 worktree 完成，主 checkout 不切分支；合併與提交由主代理串行處理。其他專案依其自身規則決定基底，不能把本 repo 的 `main` 推廣到其他 repo。
- 修改 Codex 行為從 `codex/` 的來源下手。只有修改共同用途或安裝入口時才碰根檔；來源與 live `~/.codex`、`~/.agents/skills` 是不同部署位置。
- 工作流程式、技能、agent 與安裝說明進 Git；credentials、auth、sessions、SQLite、備份、log、使用者的個人設定不進 Git。
- 不把工作區已有的 `settings.json` 個人變更加入任務提交。逐檔 stage，驗收與 review 後 commit；push 必須獲得 Mike 明確授權。

## Codex 適配

- 使用當前 runtime 提供的 subagents、worktree、review 與 approval 能力；CLI 的 fallback 要明確記錄。不要以改名的方式搬用 Claude 的 teammate、trust-dir、cmux 或模型名稱。
- `codex/assets/AGENTS.md` 是要部署的規則資產；本檔只指導來源專案的開發，不代表已安裝或已核准 live hooks。
- Hook 接口遵照官方 canonical payload。對 `apply_patch` 解析 patch 指令，不能只找 `file_path`；不回傳尚未支援的 `permissionDecision: "ask"`。
- 安裝器預設 dry-run；明確套用前先完成衝突檢查，替換既有資產需要可還原備份。只能管理本套資產，保留其他 config、MCP、plugins、model 與 runtime 資料。Hook 定義需經 Codex 的 trust review。

## 驗收

- Python 腳本以 Python 3.9+ 標準庫可執行。
- build/asset 檢查：`python3 codex/validate.py`。
- fixtures：`python3 -m unittest discover -s codex/tests -v`。
- 安裝與 hook 測試僅用臨時目錄與假的 formatter；不安裝到 live 目錄，不執行真實破壞命令、migration 或 nginx 操作。
- Review 對照此次任務規格與實際 diff；涉及權限、secrets 或 guard 的修改加做 security review。未覆蓋的 runtime 行為如實記錄，不把檔案存在當作保障有效。
