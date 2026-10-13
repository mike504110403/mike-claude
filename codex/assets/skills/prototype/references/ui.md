# UI Prototype

優先在真實現有host page上做variant，保留現實密度／layout與上下文；若真無host才新throwaway route，遵循repo路由且命名prototype。route modification仍在feature worktree，不能直接改主checkout。

一般2到3個結構明顯不同方案，用 `?variant=`或清楚switcher切換；差異應在information hierarchy／density／interaction，不只是顏色。無後端需求就合成資料；需要真實讀取／auth用local-stack且標授權／隔離狀況。

每個variant顯示問題、假設與主要state，能對照loading/error/empty/ready；不新增持久寫入或複雜abstraction。沿repo已有script一條命令啟動，App可用時開URL供Mike比較。

使用者選定後記問題／答案；移除prototype只限自己創建且已授權的精確檔案／route，別清其他人的實驗。正式整合不由原型選擇自動授權。
