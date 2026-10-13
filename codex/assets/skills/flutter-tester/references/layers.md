# Layer 測試

Repository mock其DAO/API依賴，以回傳domain結果、錯誤／cache fallback為觀測；Service mockrepository/network，不連正式端點；DAO用已有隔離in-memory DB或相容fake，查CRUD／transaction，不把fake行為當真引擎完全等價。

Mockito沿repo annotations與生成命令，不新增不必要mock；Fake適合不驗interaction的替身。SharedPreferences若使用，沿SDK版本的mock初始化。GetIt註冊限每test，tearDown await reset；DB/stream/controller都要釋放。測試fixtures獨立，時間與network不依賴個人環境。

Given-When-Then可用describe/group：Given合法資料與依賴 → When公開method → Then回傳outcome。成功、錯誤與業務邊界的expected由spec／獨立fixture決定。verify只在interaction就是契約時用，不因implementation呼叫順序而過度鎖死。
