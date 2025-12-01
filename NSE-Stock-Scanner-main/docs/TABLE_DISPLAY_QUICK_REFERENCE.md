# 📊 Table Display - Quick Reference Card

## 🚀 Quick Start (Copy & Paste)

### Import
```python
from helpers.table_display import (
    display_table_styled,
    display_table_simple,
    display_table_plotly,
    display_table_summary_stats,
    show_best_performers,
    show_worst_performers,
)
```

---

## 📋 5 Ways to Display Tables

### 1. Styled HTML (Recommended)
```python
display_table_styled(results_df, title="Results", max_rows=10)
```
**Output:** Color-coded table with green/yellow/red gradients  
**Best for:** Reports, presentations  
**Time:** Instant

### 2. Simple Text
```python
display_table_simple(results_df, title="Quick View", max_rows=10)
```
**Output:** Plain text table  
**Best for:** Quick overview, debugging  
**Time:** Instant

### 3. Interactive Plotly
```python
display_table_plotly(results_df, title="Interactive", max_rows=10)
```
**Output:** Beautiful interactive table  
**Best for:** Presentations, dashboards  
**Time:** 1-2 seconds

### 4. Summary Stats
```python
display_table_summary_stats(results_df, title="Summary")
```
**Output:** Key metrics and statistics  
**Best for:** Executive overview  
**Time:** Instant

### 5. Quick Best/Worst
```python
show_best_performers(results_df, metric='win%', top_n=10)
show_worst_performers(results_df, metric='ROI', top_n=5)
```
**Output:** Top N and bottom N sorted  
**Best for:** Finding winners/losers  
**Time:** Instant

---

## 🎯 Common Use Cases

### Display Backtest Results
```python
# Show full results with colors
display_table_styled(results, max_rows=20)

# Get quick stats
display_table_summary_stats(results)

# See top performers
show_best_performers(results, top_n=10)
```

### Compare Two Strategies
```python
display_table_comparison(
    macd_results,
    rsi_results,
    title1="MACD Strategy",
    title2="RSI Strategy"
)
```

### Focus on Profitable Stocks
```python
# Filter: ROI > 0
profitable = results[results['ROI'] > 0]
display_table_styled(profitable, title="Profitable Stocks")
```

### Show Only High Win-Rate Stocks
```python
# Filter: win% > 60%
high_win = results[results['win%'] > 0.60]
display_table_styled(high_win, title="🏆 >60% Win Rate")
```

---

## 🎨 Customization

### Change Number of Rows
```python
display_table_styled(results, max_rows=5)   # Show first 5
display_table_styled(results, max_rows=None) # Show all
```

### Highlight Specific Columns
```python
display_table_styled(
    results,
    highlight_cols=['win%', 'ROI', 'gains']
)
```

### Export to CSV
```python
results.to_csv('backtest_results.csv')
```

### Export to Excel
```python
results.to_excel('backtest_results.xlsx')
```

---

## 📊 Column Reference

For backtest results:

| Column | Example | Meaning |
|--------|---------|---------|
| **win%** | 0.65 | 65% of trades were profitable |
| **ROI** | 8.25 | 8.25% return on investment |
| **wins** | 13 | 13 profitable trades |
| **losses** | 7 | 7 losing trades |
| **buys** | 20 | 20 buy signals |
| **holds** | 15 | Average 15 days per trade |

---

## ⚡ Pro Tips

### Combine Multiple Views
```python
# Executive summary
display_table_summary_stats(results)

# Top performers detail
show_best_performers(results, top_n=5)

# Full data with colors
display_table_styled(results, max_rows=20)
```

### Filter + Display
```python
# Winners only
winners = results[results['win%'] >= 0.50]
display_table_styled(winners, title="🏆 Winning Strategies")

# Losers only
losers = results[results['ROI'] < 0]
display_table_styled(losers, title="📉 Strategies to Avoid")
```

### Custom Title with Emoji
```python
display_table_styled(results, title="🎯 MACD Strategy Results")
display_table_simple(results, title="💰 Profitable Trades")
display_table_plotly(results, title="📈 Interactive Analysis")
```

---

## 🔄 Full Workflow Example

```python
from helpers.backtest import Backtest
from helpers.table_display import (
    display_table_styled,
    display_table_summary_stats,
    show_best_performers
)

# 1. Run backtest
bt = Backtest()
results = bt.backtest(strategy='macd', stocks='nifty_50', top_n=20)

# 2. Display results
display_table_styled(results, title="MACD Backtest Results")

# 3. Get summary
display_table_summary_stats(results, title="Performance Summary")

# 4. Show winners
show_best_performers(results, metric='win%', top_n=10)

# 5. Export
results.to_csv('macd_results.csv')
```

---

## ✅ Checklist

- [ ] Import table display functions
- [ ] Run your analysis/backtest
- [ ] Display results with `display_table_styled()`
- [ ] Get summary stats with `display_table_summary_stats()`
- [ ] Find best performers with `show_best_performers()`
- [ ] Export to CSV/Excel if needed
- [ ] Share results with stakeholders

---

## 🎯 Choose Your Display

**Need quick view?** → `display_table_simple()`  
**Need professional look?** → `display_table_styled()`  
**Need presentation?** → `display_table_plotly()`  
**Need key metrics?** → `display_table_summary_stats()`  
**Need best/worst?** → `show_best_performers()` + `show_worst_performers()`

---

## 📞 Common Issues

**"Table looks plain"** → Use `display_table_styled()` instead  
**"Takes too long"** → Reduce `max_rows` parameter  
**"Too many columns"** → Filter DataFrame first: `results[['col1', 'col2']]`  
**"Want to export"** → Use `results.to_csv('file.csv')` or `to_excel()`

---

**Ready to display tables professionally?** Copy the import statement above and start using! 🚀
