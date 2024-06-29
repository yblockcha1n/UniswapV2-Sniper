# UniswapV2-Sniper

https://www.youtube.com/watch?v=NU0HtzAC6-o

## Workflow

```mermaid
graph TD
    A[Start] --> B[監視: getReserves関数の呼び出し]
    B --> C{関数呼び出し検出?}
    C -->|Yes| D[swapExactETHForTokens関数を呼び出して購入]
    C -->|No| B
    D --> E[Approve実行]
    E --> F[getAmountOuts関数でトークン算出シミュレーション]
    F --> G{指定倍数に到達?}
    G -->|No| F
    G -->|Yes| H[swapExactTokensForETH関数を呼び出して売却]
    H --> I[End]
```
