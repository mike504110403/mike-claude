---
name: owasp-mobile-security-checker
description: 對 Flutter／mobile 做明確要求的安全稽核；依 OWASP Mobile Top 10 證據區分弱點與線索。
---

# Mobile 安全稽核

適用Flutter/Dart與Android/iOS mobile範圍，先確認使用者要求的資產／版本、允許的靜態／動態檢查與交付。一般工程不自動啓動完整稽核或寫precommit。依 [references/mobile-top-10.md](references/mobile-top-10.md) 覆蓋所需類別。

靜態檢查用rg／已安裝secret scanner、repo已有審計工具，先查命令與輸出契約。工具沒裝可做code review，標能力差距，不自動install、對外upload或聲稱CVE完整掃描。只讀tracked/source/config，避免把credential文件內容印出。secret finding僅report path/line與遮罩，非必要不要保存真值。

依賴review以pubspec.lock解析版本為基礎，查當前primary advisory／package來源；any constraint/outdated只是線索，不等於已證明CVE。Firebase client config不必然是秘密，需分析實際權限；build-time env injection不能把已打包client secret變安全。缺pinning、root detection／obfuscation也不是自動漏洞，要有具體threat與控制缺口。

動態檢查只有獲授權測試環境／帳號；不能把個人登入profile或prod外送當審計預設。finding附威脅情境、code證據、可利用前提、影響、確信程度、修法與未驗部分。不宣佈合規認證；修復、發佈與通知各依本次授權。
