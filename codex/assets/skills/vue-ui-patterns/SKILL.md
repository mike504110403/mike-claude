---
name: vue-ui-patterns
description: Vue 3 loading、error、empty、async mutation 與資料更新的 UI 行為模式。
---

# Vue UI 狀態

遵循vue-dev的script setup TS、Pinia、既有axios、UI framework與i18n約定；不為模式新增dependency或tests。先辨初載、背景refresh、empty、error、ready與submit等狀態，別用一個loading boolean混淆全部情境。

- 初載且無可展示data才顯示主skeleton／spinner；緩存資料refresh時保留內容並顯示次要busy狀態。用 `data === undefined`區分未加載與合法空數組。
- 無資料error顯示可重試ErrorState；有資料refresh失敗保留內容並顯示banner／toast。error不能只console.log，也不能直接顯示原始secret／堆棧給用戶。
- 每個collection提供語義empty狀態，區分無專案與無搜索結果；空結果不是加載中。
- mutation先校驗，隨後busy／禁用觸發器，成功／失敗有用戶可見反饋，finally恢復狀態；避免重復submit。重試需保留用戶輸入。
- optimistic update只有能正確rollback、協調併發與驗證失敗的場景才用。不可逆或付款流程不因「更快」就偽造成功。
- 改filter／route的併發請求要AbortController（封裝支持時）或generation token防舊response覆蓋新結果；unmount清資源。響應式state處理遵循Vue機制，不猜reactive snapshot。

狀態優先序隨可用資料決定：無資料error→error；loading且未加載→loading；成功空→empty；已有data→content並附refresh／error反饋。字段級錯誤放inline，頁級錯誤用banner或full-state，可恢復通知用專案toast。所有文案使用專案i18n。

檢查每條用戶操作的loading／成功／失敗、可重試性、重復submit與舊response競態；這些是行為設計清單，不構成自動新增test文件／實跑授權。實際驗收依vue-dev與此次請求。
