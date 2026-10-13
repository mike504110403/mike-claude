# Collection 政策

## 結構與排序

Collection 放既有約定的 bruno/，保留 bruno.json、路由 group 資料夾、各層 folder.bru及 MANIFEST.md。MANIFEST列 METHOD、完整path、auth、handler/source行號、request檔與排除原因。group前綴需算入path，被註解或未註冊route不收。

實體名稱沿用 kebab-case；meta.name與folder顯示名採專案領域語言。依角色分組，已有業務大類則保留；不能為此次窄增量整包搬家。每個角色的登入簽發端點置頂 login/（seq最前）；已有明確例外歸屬就保留並在role docs標位置，不能重複收錄。登出／改密碼仍留原業務group。request及group的seq按route註冊順序，新增插入對應位置，不能全部append末尾。

## Auth 與 secrets

以實際middleware判斷認證。角色folder集中Bearer／共用header，request用inherit；先確認所用Bruno版本是否遞迴繼承。公開／登入endpoint明設none。HMAC與WS auth按實作，不能假設Bearer；WS用原生request類型及獨立wsBaseUrl，不用GET假裝。

environments/*.bru.example可追蹤，所有secret/token/username/password值留空；實際 environments/*.bru與可能持有token的collection.bru不追蹤。首次使用複製example到本機檔並填本機secret。各環境變數結構一致，URL從專案宣告／code核實是API target，未知就空值並標限制，不能猜online domain。

登入 post-response 若需要自動存token：依該handler實際response path、角色專屬變數存入；成功且欄位有效才寫，不能覆寫其他角色。使用者手維護的自動登入／重登腳本保留。要新增這些有副作用腳本須在需求範圍內，核實版本的script API、共用headers與避免遞迴觸發，明示重試／鎖帳與2FA限制；不把登入執行當同步驗收。一次性secret不寫入追蹤檔。

## 範例、assert與增量保護

path params、query、body與handler綁定／DTO逐欄對照，multipart等例外逐條列MANIFEST。default assert是實際成功HTTP status與專案統一封包的success code；必須查證各handler，不能固定所有API=200。不要硬驗可省略data欄位。下載只驗status；WS不套HTTP/body assert；非統一封包、2FA中間狀態逐筆記例外。

增量只碰diff涉及route／handler／DTO：先讀再更新，保護人工tests、自寫docs與範例調整。同步政策管理的assert可隨API改動更新。刪endpoint時精確移除對應檔並回報，保留無關項。排序變更限受影響group。驗收對帳method/path/auth/body及排除數，不能只以檔案數認定完整。
