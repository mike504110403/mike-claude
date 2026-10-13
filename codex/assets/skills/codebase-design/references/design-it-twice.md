# 比較替代介面

只在使用者要探索interface alternatives時使用。先固定問題、callers、invariants、依賴分類與不能改的constraints，再比較至少兩個實質不同方案。

有原生subagent且本次允許delegation時，按可用slot派唯讀設計代理；沒有就依序設計。不要承諾固定3+代理或填Claude工具／model。各brief自足：source路徑與行號、domain vocabulary、interface約束、依賴與ownership、不改code。

可分別優化：最小entrypoint與參數、常見caller最簡單、真實多用途彈性、cross-seam adapter。每案交interface（含error/ordering/config）、caller例子、隱藏的複雜度、adapter策略與trade-off。

用depth／locality／seam位置比較，給有依據的推薦或可行hybrid；不能因比較完成就開始implement。只有使用者要求落地才轉工程lane。
