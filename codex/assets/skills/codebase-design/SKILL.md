---
name: codebase-design
description: 設計 module 介面、深度與 seam；需要降低呼叫端複雜度或提升可驗證性時使用。
---

# Deep modules

共同語彙：Module 是有 interface 與 implementation 的函式／類別／package；Interface 包含簽章、invariants、ordering、error modes、配置與performance約束；Implementation 是內部實作。Depth 是呼叫者學一份interface可取得多少行為能力，不是程式碼行數比。

Seam 是不修改該處就能替換行為的位置；Adapter 是滿足該seam interface的具體實作。Leverage指呼叫者獲得的能力，Locality指修改、錯誤與驗證集中在何處。用專案CONTEXT的領域詞命名，避免為詞彙教條重命名既有code。

設計時問：能減少entrypoints與參數嗎？能把呼叫者現在必須知道的複雜度藏入module嗎？刪除此module後，複雜度是消失還是分散到N個caller？若只是消失，可能是無價值轉接。

Interface也是可觀測的test surface；依賴可注入、純計算可回傳結果，但不為測試把內部細節外曝。一個adapter不自動證明需抽象；兩個真實用途才是較強的變動證據。

依賴分類與deepening時讀 [references/deepening.md](references/deepening.md)。使用者要求比較替代介面時讀 [references/design-it-twice.md](references/design-it-twice.md)，不自動開始多代理設計或實作。
