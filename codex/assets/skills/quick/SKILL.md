---
name: quick
description: 處理範圍一眼可界定的小型工程改動；主代理直接實作。
---

# quick

定義目標與驗收；確認不碰金流、認證、secrets、migration、全域配置或不可逆操作。使用 feature-flow 建 worktree，實作後用 verify 親驗。若影響面擴大立即升級；驗收通過再 commit，push 另走 ship。
