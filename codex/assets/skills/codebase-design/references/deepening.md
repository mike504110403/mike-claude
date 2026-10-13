# Deepening 的依賴與 seam

| 依賴 | 策略 |
| --- | --- |
| In-process 計算／state | 集中到deep module，透過public interface觀測，不需憑空adapter |
| Local-substitutable DB／FS | 若已有相容本機替身，在internal seam替換；指出替身不能覆蓋的差異 |
| Remote but owned | 邏輯集中，transport以port／adapter注入，production與隔離測試用途都要有依據 |
| True external | 對第三方port注入mock／fake，驗契約與異常，不模擬不存在的保證 |

內部seam不必變成external interface。只有單一adapter時先問抽象是否真有用途，不為「將來可能」新增port。測試若已授權，集中在新interface並驗可觀測outcome；舊測試只有在行為覆蓋被證明取代且在範圍內才刪，不能照規則一次刪所有unit tests。

深化報告需source caller證據、現有interface負擔與新形狀隱藏什麼。不同deployment不阻止邏輯集中，但network failure、ordering與ownership仍是interface的一部分。
