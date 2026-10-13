---
name: pdf
description: 讀 PDF 時轉成 Markdown 中間檔後讀片段；需要圖／版面時另存影像。
---

# PDF 轉檔後讀取

先把本文轉 Markdown 到明確的本機中間檔，再以 rg／sed讀相關片段。不要原生整份PDF讀取導致所有頁圖片進 context。中間檔與原文件同樣敏感，放scratch且不進Git；除非使用者要求持久產物。

內附可攜轉換器 [scripts/pdf2md.py](scripts/pdf2md.py)：Python 3.9+標準庫入口，轉換依賴本機 `pymupdf4llm`／`pymupdf`。以已安裝套件的Python interpreter執行，不依賴固定shebang／venv。缺依賴回報並停止，不自動pip、uv或下載OCR語言包。

```sh
python3 <skill-dir>/scripts/pdf2md.py <input.pdf> -o <scratch/output.md>
python3 <skill-dir>/scripts/pdf2md.py <input.pdf> -o <scratch/pages.md> -p 1-20
```

`-p`採1-based range或逗號列表；輸出metadata列實際頁數與選頁，stdout只列路徑、頁數、字元與文字密度，PDF正文寫入指定.md而非stdout。已有輸出預設拒絕覆寫，可在核實後加 `--overwrite`。需要圖以 `--images <scratch/images-dir>`另存；必須指定尚不存在的專用目錄，既有路徑／symlink 一律拒絕，不收緊共享目錄。新目錄採 0700，子程序以 private umask 產圖並確認輸出為 regular files、收緊至 0600；按工具／工作流影像觀測規則判讀。失敗時可能留有私密目錄內的部分圖片，重試需使用新的路徑，刪除依使用者授權。

文字密度是觀測，不是OCR完成的證據。稀疏可能是掃描或圖表／投影片；抽讀.md確認。OCR能力依套件版本與本機Tesseract／語言包，未配置時如實回報；不要宣稱自動中文OCR可靠。版本不支援圖片／轉換選項時停止，不悄悄丟內容。

子程序只產生私密 0600 staged 本文與 metadata；父程序先讀取／解析 metadata、讀取本文並準備 JSON 回報，再重新核實最終 target，透過同目錄 0600 temporary 做最後 atomic publish。metadata／本文讀取、解析、報告準備或發布前寫入失敗時保留舊檔；stdout 的 output 只指最終 target，不洩漏 scratch 路徑。拒絕跟隨輸出 symlink、覆寫 input alias 或違反 no-clobber。Windows 等平台需核實本機目錄 ACL，POSIX mode 不保證等價 ACL。轉換在隔離子程序中執行，stdout/stderr 在其整個生命週期（含 C buffered output 的退出 flush）由父程序擷取；成功 metadata 另經私密檔傳回，父程序不從轉換器 stdout 解析或重播內容。`-v` 會把可能含敏感文件資訊的 diagnostics 送往 stderr，僅排錯且核實存放位置時使用。

定位用 `rg -n <keyword> <output.md>`再 `sed -n '<start>,<end>p'`；表格跨頁分隔可能重複，查證相關段即可。回報轉換命令、選頁、限制及引用頁碼；不得把metadata成功當作本文已完整判讀。
