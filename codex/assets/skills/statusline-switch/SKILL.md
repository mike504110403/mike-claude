---
name: statusline-switch
description: 檢視或調整 Codex CLI status line；App 使用原生進度與 commentary。
---

# Codex Status line

先辨當前是CLI或App，以及用戶僅問狀態還是明確要求切換。本輪創建／移植skill不構成修改live config的授權。

CLI使用官方 `/statusline` 選擇支持的item IDs；其配置持久化在有效config的 `[tui] status_line`。從當前CLI版本／已有config讀取當前item，不杜撰item名單或註冊腳本dispatcher。支持的item／操作以當前 `/statusline` UI／官方文檔為準，不執行任意stdin/stdout腳本。

沒有參數時展示可觀測當前設定與工具可見選項；用戶給名稱但它是舊自訂script時，說明CLI支持item選項，並按其想看到的資訊提出可支持組合，不承諾等價腳本。明確要求切換後，優先讓CLI原生/statusline保存；若已授權直接編輯config，先備份、只改tui.status_line、保留其他config，確認所在profile／override和當前版本支持。無法操作CLI就給操作方法並標未執行，不能稱已切換。

App沒有CLI任意dispatcher接口；使用原生任務進度與commentary報告階段。不把CLI配置更動說成App statusline即時生效。

官方依據：[CLI slash commands](https://developers.openai.com/codex/cli/slash-commands)、[Config reference](https://developers.openai.com/codex/config-reference)。有更新疑問時重新覈實當前官方說明。
