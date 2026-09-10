---
name: pdf
description: 把 PDF 轉成 LLM 友善的 markdown 再讀——標題／表格／清單結構保留、內容落磁碟只讀片段。任何要讀 PDF 的任務一律先走這裡，不用原生 Read 直開 PDF。
---

# /pdf — PDF 讀取

**PDF 絕不用原生 Read 直開**——頁面會轉成圖片進 context（與截圖同一種燒法）。規則見全域「Context 預算紀律」**PDF 不直開列**，本 skill 只持有流程與指令。一律三段：**轉檔 → 落磁碟 → 讀片段**。

## 工具鏈（本機已建好；換機器需重建，見下）

| 元件 | 位置 | 說明 |
| ---- | ---- | ---- |
| 轉換器 | `~/.claude/bin/pdf2md` | pymupdf4llm 1.28.2；保留標題階層、markdown 表格、清單、程式碼區塊。**入版控** |
| 執行環境 | `~/.claude/pdf-env/`（Python 3.12 venv） | uv 建立，不污染系統 python；比照 `~/.claude/e2e/` runner 慣例。**不入版控**（`.gitignore` 全擋規則），與 e2e runner 同樣是本機設施 |
| OCR | tesseract | 無文字層的頁 **pymupdf-layout 會自動 OCR**（2026-09-10 以純圖片 PDF 實測生效，無需傳參）。**本機只有 `eng` 語言包**——中文掃描版會出亂碼，需先 `brew install tesseract-lang` |

**換機器／重裝後 venv 不存在**（`bin/pdf2md` 的 shebang 寫死 `~/.claude/pdf-env/bin/python`，會出 `bad interpreter`）→ 重建兩行：

```
uv venv --python 3.12 ~/.claude/pdf-env
uv pip install --python ~/.claude/pdf-env/bin/python pymupdf4llm
```

## 步驟

1. **轉檔**（只印 metadata，內容不進 context）：

   ```
   ~/.claude/bin/pdf2md <file.pdf> -o <out.md>
   ```

   大檔先切頁：`-p 1-20`（1-based，也吃 `3,5,7`；越界會自動夾取並在回報標出實際頁數）。排錯要看套件訊息加 `-v`（預設靜音——那些訊息一併算進 context）。

2. **看回報的「文字層」欄**——它是**觀測值不是判定**：
   - `有（每頁 N 字元）` → 直接進第 3 步。
   - `稀疏（每頁 N 字元 < 50）` → 兩種可能：真掃描版（已自動 OCR，中文需先裝語言包否則亂碼），或版面本身就稀疏（樂譜、投影片、圖表頁）。**開轉出的 .md 抽看幾行就能分辨**，別憑這欄下結論。

3. **讀片段，不整檔 Read**：`grep -n <關鍵字> <out.md>` 定位 → `sed -n '<起>,<迄>p'` 取原文。這一步是本 skill 的重點——轉檔只是讓「讀片段」變可能。

4. **要判讀圖／版面**：加 `--images` 另存圖檔，**派 subagent 看**，圖不進大腦 context。

## 紀律

- 轉出的 `.md` 是**中間產物**：放 scratchpad 或該專案 `docs/`，不進 git（除非 Mike 明說要）。
- 轉換器**只回報 metadata**（頁數、字數、輸出路徑、文字層抽樣字元密度）——這是刻意設計，別改成印內容。
- 跨頁表格的 `|---|` 分隔行可能重複出現（pymupdf4llm 對跨頁表的已知行為）——不影響 grep 定位，不用修。
- 敏感文件（合約、對帳單、含個資的規格書）轉出的 `.md` 同樣敏感：遵守該專案的遮罩規定，不進 git、不外流。
