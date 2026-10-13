---
name: writing-great-skills
description: 寫／修 Codex skills 時改善觸發、流程可預測性與按需資訊揭露。
---

# 寫出可預測的 skills

先用當前 skill-creator 格式與政策；以下是寫作原則，不代替 runtime 支援的 schema。

- description 提前說明能力與觸發條件，排除真正易誤判的鄰近任務；刪同義詞堆疊。每個 skill 保留 name/description；不搬 Claude 的 disable-model-invocation／allowed-tools。
- 自動選擇預設保留。只有使用者明確要求 explicit-only 才以受支援的 `agents/openai.yaml` 設 `policy.allow_implicit_invocation: false`；這不等於權限核准，也不阻止已授權 workflow 按需參考技能內容。
- 入口放各分支必需的決策、動作與可觀測完成條件；分支才需的內容放 references，連結文字說明何時讀。沒有實際用途的 script、範本、泛用手冊不保留。
- 相同規則只維護一處；引用須存在、可攜且有必要，不為重用把技能寫成只有一串缺席工具的 router。
- 完成條件需能判斷是否達標，例如「全部 route 有對照或逐筆說明排除」，避免只說「看起來完整」。條件依風險和任務範圍，不把每個窄任務變成全套稽核。
- scripts 解決重複且易錯的機械工作，明示依賴／輸入／輸出／失敗條件；本機路徑、credentials 和模型選擇不硬編。
- 修剪每句：是否改變下一個 Codex 的決策？是否重述已有常識？單次事故的修法不能直接變成永久普遍規則。

檢查 frontmatter、連結、工具可用性與產物邊界。要行為評估時依使用者授權選真實情境，不把文字 regex 通過當作行為正確。
