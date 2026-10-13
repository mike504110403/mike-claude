---
name: flutter-tester
description: 使用者要求在 Flutter 專案寫／修／review 測試時，依層級與 Riverpod／widget 生命週期設計有意義的檢查。
---

# Flutter 測試

先讀pubspec.yaml／lock、既有測試、FVM與repo scripts；只在測試工作已要求時用，不以涉及Flutter就自動加test。使用專案已安裝SDK與binary，缺依賴回報，不自動升級／安裝。

Given-When-Then以真實可觀測行為命名，成功／失敗與必要邊界要有獨立expected值。只mock外部或可替換依賴，不驗私有state或無關call細節。repository對DAO/API替身，DAO優先隔離in-memory DB，service對repository/network，Riverpod override服務依賴而非mock provider。

依修改面按需讀： [Layer patterns](references/layers.md)、[Riverpod](references/riverpod.md)、[Widget lifecycle](references/widgets.md)。所有container/stream/controller/DB與GetIt在teardown正確釋放，平台／尺寸override用addTearDown還原，不能失敗後留下全域污染。

Mockito mock generation僅當既有生成流程要求且依賴已存在時跑專案命令；不能預設覆蓋其他generated code。runner按專案FVM／flutter script選指定test path；coverage只在需求範圍內。回報實際命令、exit／失敗、測到／未測行為與SDK版本限制。
