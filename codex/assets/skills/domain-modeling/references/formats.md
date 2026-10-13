# Glossary 與 ADR

## CONTEXT

沿用現有context map。沒有既有檔且已要求保存時，第一個術語確定才建立。

```md
# Ordering

接收並追蹤客戶訂單的領域。

## Language

**Order**：客戶提出並由系統追蹤的購買要求。
_Avoid_：Purchase, transaction
```

每個定義一兩句，選canonical term並記易混淆同義詞。只放domain概念，implementation、一般programming詞與未決需求放其適合的文件。自然形成群組才加subheading。多context的CONTEXT-MAP列位置與已確認關係。

## ADR

沿用docs/adr或repo既有路徑，讀最高編號後遞增，不覆蓋他人草稿。短標題加一到三句描述背景、選擇與理由；只有需要才加status／alternatives／consequences。proposed與accepted必須可區分，不能把未答覆的建議存成accepted。

只有難逆、沒有context會令人意外、確有trade-off的決策值得ADR。記關鍵拒絕理由，避免之後反覆提案；可逆調參或暫時「沒時間」不用長期ADR。
