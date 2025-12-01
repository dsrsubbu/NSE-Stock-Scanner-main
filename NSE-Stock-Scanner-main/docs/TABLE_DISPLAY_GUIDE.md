# 📊 Table Display Guide for Jupyter Notebooks

## Overview

This guide explains the different ways to display DataFrame results as professional-looking tables in Jupyter notebooks.

---

## 🎯 Quick Comparison

| Display Method | Best For | Appearance | Interactivity |
|---|---|---|---|
| **Styled HTML** | Professional reports | Color-coded, formatted | Non-interactive |
| **Simple Text** | Quick overview | Plain text | Minimal |
| **Plotly Table** | Presentations | Modern, styled | Fully interactive |
| **Summary Stats** | Key metrics | Formatted text | Non-interactive |
| **Filtered View** | Focus analysis | Color-coded subset | Non-interactive |

---

## 1️⃣ Styled HTML Table (Recommended)

**Best for:** Professional reports, color-coded performance metrics, color gradients for easy comparison

### Features:
- ✅ Color gradients (green for good, red for bad)
- ✅ Formatted numbers with proper decimals
- ✅ Hover effects
- ✅ Easy to read and professional looking
- ✅ Works perfectly in Jupyter

### Code Example:

```python
from helpers.table_display import display_table_styled
import pandas as pd

# Simple usage
display_table_styled(results_df, title="Backtest Results")

# With options
display_table_styled(
    results_df,
    title="Top Performers",
    max_rows=10,  # Show only first 10 rows
    highlight_cols=['win%', 'ROI']  # Highlight these columns
)
```

### Output Example:
```
================================================================================
📊 Backtest Results
================================================================================

SYMBOL   win%    ROI     wins   losses   ...
RELIANCE 0.75   +15.23%  15      5      ...
TCS      0.70   +12.50%  14      6      ...
INFY     0.65    +8.75%  13      7      ...
```

---

## 2️⃣ Simple Text Table (Quick Overview)

**Best for:** Quick lookups, terminal-friendly output, debugging

### Features:
- ✅ Plain text format
- ✅ Very fast to render
- ✅ Easy to copy-paste
- ✅ Works in all environments

### Code Example:

```python
from helpers.table_display import display_table_simple

display_table_simple(results_df, title="Quick Summary", max_rows=10)
```

### Output Example:
```
====================================================================================================
📊 Quick Summary
====================================================================================================

                          SYMBOL  win%    ROI   wins  losses  ...
0                       RELIANCE  0.75  15.23    15       5
1                            TCS  0.70  12.50    14       6
2                           INFY  0.65   8.75    13       7

====================================================================================================
📈 Total Results: 50 | Displayed: 10
====================================================================================================
```

---

## 3️⃣ Interactive Plotly Table (Presentations)

**Best for:** Presentations, interactive exploration, professional dashboards

### Features:
- ✅ Fully interactive
- ✅ Beautiful modern design
- ✅ Professional appearance
- ✅ Great for stakeholders
- ✅ Responsive design

### Code Example:

```python
from helpers.table_display import display_table_plotly

display_table_plotly(
    results_df,
    title="Interactive Results",
    max_rows=10
)
```

### Output:
Interactive table with hover tooltips, sortable columns (when using HTML export)

---

## 4️⃣ Summary Statistics (High-Level Overview)

**Best for:** Executive summaries, understanding data at a glance

### Features:
- ✅ Key metrics at a glance
- ✅ Best/worst performers highlighted
- ✅ Performance tiers
- ✅ Statistical summary

### Code Example:

```python
from helpers.table_display import display_table_summary_stats

display_table_summary_stats(results_df, title="Backtest Analysis")
```

### Output Example:
```
================================================================================
📊 Backtest Analysis - SUMMARY STATISTICS
================================================================================

Total Entries:              50
Average Win%:               0.65 (65%)
Best Win%:                  0.95 (95%) - RELIANCE
Worst Win%:                 0.45 (45%) - INFY
Average ROI:                +8.25%
Best ROI:                   +18.50%

Performance Tiers:
  >50% Win Rate:            48
  >60% Win Rate:            35
  >70% Win Rate:            15
  100% Win Rate:            2

================================================================================
```

---

## 5️⃣ Filtered Views (Focus Analysis)

**Best for:** Finding best performers, focusing on specific criteria

### Code Example:

```python
from helpers.table_display import display_table_filtered

# Show stocks with >60% win rate
display_table_filtered(
    results_df,
    filter_col='win%',
    min_val=0.60,
    title="🏆 Stocks with >60% Win Rate"
)

# Show stocks with profitable ROI
display_table_filtered(
    results_df,
    filter_col='ROI',
    min_val=0,
    title="💰 Profitable Stocks"
)
```

---

## 6️⃣ Comparison View (Side-by-Side)

**Best for:** Comparing two strategies, before/after analysis

### Code Example:

```python
from helpers.table_display import display_table_comparison

display_table_comparison(
    macd_results,
    rsi_results,
    title1="MACD Strategy Results",
    title2="RSI Strategy Results"
)
```

---

## 🚀 Quick Preset Functions

### Best Performers

```python
from helpers.table_display import show_best_performers

# Show top 10 by win%
show_best_performers(results_df, metric='win%', top_n=10)

# Show top 5 by ROI
show_best_performers(results_df, metric='ROI', top_n=5)
```

### Worst Performers

```python
from helpers.table_display import show_worst_performers

# Show bottom 5 by win%
show_worst_performers(results_df, metric='win%', top_n=5)
```

### All Statistics at Once

```python
from helpers.table_display import show_all_stats

show_all_stats(results_df, title="Complete Analysis")
```

This shows:
1. Full dataset (styled)
2. Summary statistics
3. Top 10 performers
4. Bottom 10 performers

---

## 📝 Practical Workflows

### Workflow 1: Backtest Results Analysis

```python
from helpers.table_display import (
    display_table_styled,
    display_table_summary_stats,
    show_best_performers
)

# Run backtest
results = backtest_engine.run(strategy='macd')

# 1. See full results
display_table_styled(results, max_rows=15)

# 2. Get summary
display_table_summary_stats(results)

# 3. Focus on winners
show_best_performers(results, top_n=10)
```

### Workflow 2: Strategy Comparison

```python
from helpers.table_display import (
    display_table_comparison,
    display_table_summary_stats
)

# Run two strategies
macd = backtest_engine.run(strategy='macd')
rsi = backtest_engine.run(strategy='rsi')

# Compare side-by-side
display_table_comparison(macd, rsi, "MACD", "RSI")

# Get summary of each
display_table_summary_stats(macd, "MACD Strategy")
display_table_summary_stats(rsi, "RSI Strategy")
```

### Workflow 3: Focus on Best Opportunities

```python
from helpers.table_display import (
    display_table_filtered,
    show_best_performers,
    show_worst_performers
)

# Run backtest
results = backtest_engine.run()

# Find high-win-rate stocks
display_table_filtered(results, 'win%', min_val=0.70)

# Also check low performers
show_worst_performers(results, top_n=5)
```

---

## 🎨 Customization Options

### Change Color Scheme

The default uses 'RdYlGn' (Red-Yellow-Green) gradient. You can modify the helper function to use other colormaps:

```python
# In display_table_styled(), change this line:
styled = styled.background_gradient(subset=[col], cmap='RdYlGn')

# To use other colormaps like:
# 'YlOrRd' - Yellow-Orange-Red (good for losses)
# 'YlGn' - Yellow-Green (good for gains)
# 'Blues' - Blue gradient
# 'Greens' - Green gradient
```

### Custom Formatting

Modify format_dict in `display_table_styled()`:

```python
format_dict = {
    'win%': '{:.2%}',       # 65.00%
    'ROI': '{:+.2f}%',      # +8.25%
    'price': '₹{:,.2f}',    # ₹2,850.50
    'volume': '{:,.0f}',    # 1,250,000
}
```

---

## 💡 Pro Tips

### Tip 1: Combine Multiple Views
```python
# Show both styled and text views
display_table_styled(results, max_rows=10)
display_table_summary_stats(results)
display_table_simple(results.head(5))
```

### Tip 2: Export to CSV
```python
# Export top performers
top_performers = results[results['win%'] > 0.70]
top_performers.to_csv('best_stocks.csv')
```

### Tip 3: Export to Excel
```python
# Export with formatting (requires openpyxl)
top_performers.to_excel('results.xlsx', sheet_name='Top Performers')
```

### Tip 4: Chain Multiple Filters
```python
# Find stocks with high win% AND positive ROI
filtered = results[(results['win%'] > 0.60) & (results['ROI'] > 0)]
display_table_styled(filtered, title="High Win% & Positive ROI")
```

---

## 🔍 Column Descriptions

For backtest results, typical columns are:

| Column | Description |
|--------|-------------|
| **SYMBOL** | Stock ticker symbol |
| **win%** | Win percentage (trades with profit / total trades) |
| **ROI** | Return on Investment percentage |
| **wins** | Number of winning trades |
| **losses** | Number of losing trades |
| **buys** | Total buy signals |
| **sells** | Total sell signals |
| **buy_date** | List of buy dates |
| **sell_date** | List of sell dates |
| **buy_price** | List of buy prices |
| **sell_price** | List of sell prices |
| **p&l** | Profit & loss for each trade |
| **hold_period** | Days between buy and sell |

---

## ❓ FAQ

**Q: Which display method should I use?**  
A: Use `display_table_styled()` for most cases. It looks professional and is easy to read.

**Q: Can I use these in other Python notebooks (not Jupyter)?**  
A: The IPython functions require Jupyter. For plain Python, use `display_table_simple()`.

**Q: How do I save the table as an image?**  
A: For Plotly tables: Right-click and select "Save image". For HTML styled tables, use Jupyter's export to PDF.

**Q: Can I customize the colors?**  
A: Yes! Modify the `cmap` parameter in `display_table_styled()` or edit the helper function.

**Q: How do I display very large DataFrames?**  
A: Use `max_rows` parameter or filter the data first.

---

## 📚 Related Functions

Check out these related functions in `helpers/table_display.py`:

- `format_currency()` - Format numbers as currency
- `format_percentage()` - Format numbers as percentage
- `create_summary_dict()` - Create dictionary of summary stats

---

## 🎯 Next Steps

1. Import the helper functions in your notebook
2. Choose the display method that suits your needs
3. Customize with options like `title`, `max_rows`, `highlight_cols`
4. Combine multiple display methods for comprehensive analysis

**Example:**
```python
from helpers.table_display import (
    display_table_styled,
    display_table_summary_stats,
    show_best_performers,
)

# Your analysis code here
results = run_backtest()

# Display results
display_table_styled(results)
display_table_summary_stats(results)
show_best_performers(results)
```

---

Happy analyzing! 📊✨
