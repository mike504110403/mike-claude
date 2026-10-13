# OWASP Mobile Top 10（2024）檢查面

以[OWASP官方清單](https://owasp.org/www-project-mobile-top-10/)為分類基準，範圍／要求因產品threat model而異。下列是code review入口，不能當已完成全類別scanner。

| 類別 | 需查證的實際風險 |
| --- | --- |
| M1 Improper Credential Usage | client binary／log中的特權長效secret、權限範圍與token生命週期；公開client識別值不自動當secret |
| M2 Inadequate Supply Chain Security | lock版本、來源／完整性、已證實advisory、build依賴；outdated不等於CVE |
| M3 Insecure Authentication/Authorization | server-side authorization、session expiry/revoke、MFA流程與跨帳號資源控制；UI隱藏不是授權 |
| M4 Insufficient Input/Output Validation | 深連結、WebView橋接／origin、untrusted input與資料輸出處理 |
| M5 Insecure Communication | 正式target TLS／憑證驗證、cleartext exceptions、敏感傳輸；本機HTTP例外需對照build配置 |
| M6 Inadequate Privacy Controls | 個資log/analytics、過度權限、consent與資料最小化 |
| M7 Insufficient Binary Protections | 真正有關的tamper/repackaging威脅、release artifacts／符號；不把obfuscation當secret安全保障 |
| M8 Security Misconfiguration | release debug flags、exported components、ATS/NSC exceptions與WebView設定 |
| M9 Insecure Data Storage | 敏感值的SharedPreferences/file/DB/backup保護與Keychain/Keystore用途；非敏感theme偏好不算弱點 |
| M10 Insufficient Cryptography | key管理、隨機性、nonce/IV、算法／mode、hash用途；MD5校驗檔案不能直接等同密碼hash缺陷 |

證據跨Dart、Android manifest/network-security、iOS plist/entitlements及實際release配置。不要因某個keyword未命中就宣稱安全。真正確認secret時不展示值，rotate／revocation需另取得權限。整體report列已檢查／未檢查類別、可利用條件與證據。
