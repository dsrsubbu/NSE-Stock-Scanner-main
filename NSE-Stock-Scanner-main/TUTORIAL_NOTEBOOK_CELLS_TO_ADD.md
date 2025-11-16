# Add These Cells to Tutorial.ipynb

## 📌 Copy and paste these cells after your initialization section

---

## CELL: Load Bhavcopy Data from Parquet (Fast!)

```python
import pandas as pd
from pathlib import Path

# Load latest bhavcopy (Parquet format - FAST!)
latest_parquet = sorted(Path('./data_bhavcopy').glob('*.parquet'))[-1]
df_bhavcopy = pd.read_parquet(latest_parquet)

print(f"✅ Loaded bhavcopy from {latest_parquet.name}")
print(f"   Shape: {df_bhavcopy.shape} ({df_bhavcopy.shape[0]:,} stocks, {df_bhavcopy.shape[1]} columns)")
print(f"   Date: {df_bhavcopy['DATE'].iloc[0]}")
print(f"   Sample stocks: {', '.join(df_bhavcopy['SYMBOL'].head(5).tolist())}")
```

---

## CELL: Load Multiple Days (30 Days)

```python
from pathlib import Path
import pandas as pd

# Load last 30 days of bhavcopy data
parquet_files = sorted(Path('./data_bhavcopy').glob('*.parquet'))[-30:]
dfs = [pd.read_parquet(f) for f in parquet_files]
df_bhavcopy_30d = pd.concat(dfs, ignore_index=True)

print(f"✅ Loaded {len(parquet_files)} days of bhavcopy data")
print(f"   Total rows: {len(df_bhavcopy_30d):,}")
print(f"   Unique symbols: {df_bhavcopy_30d['SYMBOL'].nunique()}")
print(f"   Date range: {df_bhavcopy_30d['DATE'].min()} to {df_bhavcopy_30d['DATE'].max()}")
```

---

## CELL: Use BhavcopyHandler (Recommended)

```python
from helpers.bhavcopy_handler import BhavcopyHandler

# Initialize handler
handler = BhavcopyHandler()

# Load latest bhavcopy
df = handler.load_parquet()

# Get top gainers and losers
gainers = handler.get_top_gainers(top_n=10)
losers = handler.get_top_losers(top_n=10)

print(f"✅ Top 10 Gainers:")
print(gainers[['SYMBOL', 'CHANGE_PERCENT', 'CLOSE_PRICE', 'TTL_TRD_QNTY']])

print(f"\n✅ Top 10 Losers:")
print(losers[['SYMBOL', 'CHANGE_PERCENT', 'CLOSE_PRICE', 'TTL_TRD_QNTY']])
```

---

## CELL: Get Specific Stock History (30 days)

```python
from helpers.bhavcopy_handler import BhavcopyHandler

handler = BhavcopyHandler()

# Get RELIANCE data for last 30 days
reliance = handler.get_symbol_data('RELIANCE', days=30)

print(f"✅ RELIANCE Data (Last 30 Days):")
print(reliance[['DATE', 'OPEN_PRICE', 'HIGH_PRICE', 'LOW_PRICE', 'CLOSE_PRICE', 'TTL_TRD_QNTY']])

print(f"\n📊 Statistics:")
print(f"  Avg Volume: {reliance['TTL_TRD_QNTY'].mean():,.0f}")
print(f"  Avg Price: {reliance['CLOSE_PRICE'].mean():.2f}")
print(f"  Price Range: {reliance['CLOSE_PRICE'].min():.2f} - {reliance['CLOSE_PRICE'].max():.2f}")
```

---

## CELL: Volume Analysis

```python
from helpers.bhavcopy_handler import BhavcopyHandler

handler = BhavcopyHandler()

# Analyze volume for TCS
tcs_volume = handler.get_volume_analysis('TCS', days=30)

print(f"✅ TCS Volume Analysis (Last 30 Days):")
print(tcs_volume)

# Get top volume stocks
print(f"\n📊 Top 10 Volume Stocks Today:")
df_today = handler.load_parquet()
top_volume = df_today.nlargest(10, 'TTL_TRD_QNTY')[['SYMBOL', 'CLOSE_PRICE', 'TTL_TRD_QNTY', 'TURNOVER_LACS']]
print(top_volume)
```

---

## CELL: Compare CSV vs Parquet Loading (Performance)

```python
import time
import pandas as pd
from pathlib import Path

print("⏱️  Performance Comparison: CSV vs Parquet")
print("="*60)

# Get a test file
csv_file = list(Path('./data_bhavcopy').glob('*.csv'))[0]
parquet_file = csv_file.with_suffix('.parquet')

# Time CSV load
start = time.time()
df_csv = pd.read_csv(csv_file)
csv_time = time.time() - start

# Time Parquet load
start = time.time()
df_parquet = pd.read_parquet(parquet_file)
parquet_time = time.time() - start

print(f"CSV load time:       {csv_time*1000:.2f} ms")
print(f"Parquet load time:   {parquet_time*1000:.2f} ms")
print(f"Speedup:             {csv_time/parquet_time:.1f}x faster ⚡")
print()
print(f"CSV file size:       {csv_file.stat().st_size / 1024 / 1024:.2f} MB")
print(f"Parquet file size:   {parquet_file.stat().st_size / 1024 / 1024:.2f} MB")
print(f"Compression:         {(1 - parquet_file.stat().st_size / csv_file.stat().st_size) * 100:.0f}%")
print()
print(f"Data points loaded:  {len(df_csv):,} rows × {len(df_csv.columns)} columns")
```

---

## CELL: Analysis Example - Top Gainers/Losers with Charts

```python
from helpers.bhavcopy_handler import BhavcopyHandler
import plotly.express as px
import pandas as pd

handler = BhavcopyHandler()

# Get top movers
gainers = handler.get_top_gainers(top_n=15)
losers = handler.get_top_losers(top_n=15)

# Create visualization for gainers
fig_gainers = px.bar(
    gainers,
    x='CHANGE_PERCENT',
    y='SYMBOL',
    orientation='h',
    title='Top 15 Gainers',
    color='CHANGE_PERCENT',
    color_continuous_scale='RdYlGn',
    labels={'CHANGE_PERCENT': 'Change %', 'SYMBOL': 'Stock'}
)
fig_gainers.show()

# Create visualization for losers
fig_losers = px.bar(
    losers,
    x='CHANGE_PERCENT',
    y='SYMBOL',
    orientation='h',
    title='Top 15 Losers',
    color='CHANGE_PERCENT',
    color_continuous_scale='RdYlGn_r',
    labels={'CHANGE_PERCENT': 'Change %', 'SYMBOL': 'Stock'}
)
fig_losers.show()
```

---

## CELL: Sector Performance Analysis

```python
from helpers.bhavcopy_handler import BhavcopyHandler
import pandas as pd

handler = BhavcopyHandler()
df = handler.load_parquet()

# Get sector/series statistics
print("📊 Performance by Series (Sector):")
series_stats = df.groupby('SERIES').agg({
    'CLOSE_PRICE': ['mean', 'min', 'max'],
    'TTL_TRD_QNTY': ['mean', 'sum'],
    'SYMBOL': 'count'
}).round(2)

series_stats.columns = ['Avg Price', 'Min Price', 'Max Price', 'Avg Volume', 'Total Volume', 'Count']
print(series_stats)
```

---

## CELL: Stock Comparison (Multiple Stocks)

```python
from helpers.bhavcopy_handler import BhavcopyHandler
import pandas as pd
import plotly.graph_objects as go

handler = BhavcopyHandler()

# Get data for multiple stocks (last 30 days)
stocks = ['RELIANCE', 'TCS', 'INFY', 'ICICIBANK', 'HDFC']
days = 30

fig = go.Figure()

for stock in stocks:
    try:
        df_stock = handler.get_symbol_data(stock, days=days)
        fig.add_trace(go.Scatter(
            x=df_stock['DATE'],
            y=df_stock['CLOSE_PRICE'],
            mode='lines',
            name=stock
        ))
    except:
        print(f"Stock {stock} not found")

fig.update_layout(
    title=f'Stock Price Comparison (Last {days} Days)',
    xaxis_title='Date',
    yaxis_title='Close Price',
    hovermode='x unified'
)
fig.show()
```

---

## CELL: Export Data to CSV (if needed)

```python
from helpers.bhavcopy_handler import BhavcopyHandler
from pathlib import Path

handler = BhavcopyHandler()

# Load and export specific data
df = handler.load_parquet()

# Export top gainers to CSV
gainers = handler.get_top_gainers(top_n=20)
gainers.to_csv('./gainers.csv', index=False)
print("✅ Exported top gainers to gainers.csv")

# Export specific symbol data
reliance = handler.get_symbol_data('RELIANCE', days=60)
reliance.to_csv('./reliance_60d.csv', index=False)
print("✅ Exported RELIANCE 60-day data to reliance_60d.csv")
```

---

## 📝 Notes for Integration

1. **Add these cells** after your initialization section (after DH, In, Intra, NSE initialization)

2. **They use** the `BhavcopyHandler` class from `helpers/bhavcopy_handler.py`

3. **They load from** Parquet files (`.parquet` extension) - much faster than CSV!

4. **No additional setup** needed - files are already converted

5. **Tested with:** pandas, plotly, numpy (all standard packages)

---

## ✅ Example Output

Running these cells will show:
- ✅ Bhavcopy data loaded (3049 stocks, 15 columns)
- ✅ Date information
- ✅ Top 10 gainers/losers with percentage change
- ✅ Volume and price analysis
- ✅ Interactive charts
- ✅ Performance comparison (10x+ faster with Parquet!)

---

## 🚀 Quick Copy-Paste

If you just want ONE cell to start:

```python
# MINIMAL EXAMPLE - Copy this to get started
from helpers.bhavcopy_handler import BhavcopyHandler

handler = BhavcopyHandler()
df = handler.load_parquet()

print(f"Loaded {len(df):,} stocks from {df['DATE'].iloc[0]}")
print(df.head())
```

That's it! You're ready to analyze bhavcopy data with Parquet! ⚡
