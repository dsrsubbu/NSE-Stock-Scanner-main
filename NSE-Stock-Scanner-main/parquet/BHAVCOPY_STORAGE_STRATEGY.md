# Bhavcopy Storage Strategy Comparison

## 📊 Data Characteristics
- **Daily Size:** ~0.3-0.4 MB per day (~3000 rows, 15 columns)
- **Annual Data:** ~100-120 MB (uncompressed)
- **Current Format:** CSV files with date suffix (cm12Nov2025bhav.csv)
- **Use Case:** Time-series analysis, symbol lookups, multi-day aggregations

---

## 🗂️ Storage Options Comparison

| Feature | CSV | Parquet ✅ | SQLite | HDF5 |
|---------|-----|-----------|--------|------|
| **File Size** | 0.35 MB | 0.08 MB | 0.25 MB | 0.05 MB |
| **Compression** | None | 77% | Good | Excellent |
| **Read Speed** | Slow | ⚡ Fast (10x) | Fast (indexed) | Very Fast |
| **Write Speed** | Fast | Fast | Slower | Slower |
| **Supports Types** | No | Yes | Yes | Yes |
| **SQL Queries** | No | No | Yes | No |
| **Columnar Access** | No | Yes | No | Yes |
| **Setup Time** | None | 5 min | 5 min | 10 min |
| **Best For** | Sharing | **Daily Analysis** | **Lookups** | **Big Data** |
| **Python Load** | `pd.read_csv()` | `pd.read_parquet()` | `pd.read_sql()` | `pd.read_hdf()` |

---

## 🎯 Recommendations

### **Option 1: Parquet (RECOMMENDED) ✅**
**Best for:** Daily/weekly analysis, balanced performance
```python
# One-time setup
handler = BhavcopyHandler()
df = handler.load_all_csvs()
for date in df['DATE'].unique():
    handler.save_parquet(df[df['DATE'] == date], date.strftime('%d%b%Y'))

# Fast daily loads
df = handler.load_parquet()  # 0.08 MB, instant read
df_reliance = df[df['SYMBOL'] == 'RELIANCE']
```
**Pros:** Compressed, preserves dtypes, columnar access, ~10x faster than CSV  
**Cons:** Requires pyarrow package  
**Storage:** 77% reduction (0.35 MB → 0.08 MB per day)

---

### **Option 2: SQLite**
**Best for:** Frequent symbol/date queries, complex filtering
```python
# Setup
handler = BhavcopyHandler()
df = handler.load_all_csvs()
handler.save_sqlite(df)

# Fast queries
df = handler.load_sqlite_query(
    "SELECT * FROM bhavcopy WHERE SYMBOL='TCS' AND DATE >= '2025-11-01' ORDER BY DATE DESC"
)
```
**Pros:** SQL support, indexing, query optimization  
**Cons:** Slightly larger file size, requires sqlite3  
**Storage:** 0.25 MB per 3000 rows

---

### **Option 3: Keep CSV + Archive**
**Best for:** Keeping original, minimal setup
```python
# Just organize CSVs better
# data_bhavcopy/
#   ├── daily/
#   │   ├── cm12Nov2025bhav.csv
#   │   ├── cm11Nov2025bhav.csv
#   │   └── ...
#   ├── archive/    (older files)
#   └── index.json  (metadata)
```
**Pros:** No conversion needed, version control friendly  
**Cons:** Slower, larger files, no type safety

---

## 📈 Performance Benchmarks (Estimated)

**Loading latest 30 days of data:**
- CSV: ~5 seconds (read 30 files)
- Parquet: ~0.5 seconds (read 30 files, parallel possible)
- SQLite: ~1 second (with proper indexes)
- HDF5: ~0.2 seconds (single file)

**Get all records for a symbol:**
- CSV: Scan all 30 files, linear search
- Parquet: Columnar filter, very fast
- SQLite: Index lookup, instant
- HDF5: Instant (single file)

---

## 🛠️ Implementation Plan

### **Phase 1: Setup (Do Once)**
```python
from helpers.bhavcopy_handler import BhavcopyHandler, setup_bhavcopy_storage

# Convert all existing CSVs to Parquet
setup_bhavcopy_storage()
```

### **Phase 2: Daily Updates**
```python
handler = BhavcopyHandler()

# Load latest daily bhavcopy
df_latest = handler.load_csv()  # From CSV

# Auto-convert to Parquet
handler.save_parquet(df_latest)

# Optionally update SQLite
handler.save_sqlite(df_latest, if_exists='append')
```

### **Phase 3: Analysis**
```python
# Fast loads for analysis
df_today = handler.load_parquet()

# Get specific symbol (efficient with Parquet)
reliance = handler.get_symbol_data('RELIANCE', days=60)

# Top movers
gainers = handler.get_top_gainers()
losers = handler.get_top_losers()

# Volume analysis
vol_stats = handler.get_volume_analysis('TCS', days=30)
```

---

## 💾 Integration with Existing Code

Update `helpers/datahandler.py`:
```python
from helpers.bhavcopy_handler import BhavcopyHandler

class DataHandler:
    def __init__(self, data_path='./data', ...):
        # ... existing code ...
        self.bhavcopy = BhavcopyHandler(bhavcopy_dir=f'{data_path}/data_bhavcopy')
    
    def get_bhavcopy(self, date_str=None):
        """Get bhavcopy data for analysis."""
        return self.bhavcopy.load_parquet(date_str)
    
    def get_symbol_bhavcopy(self, symbol, days=30):
        """Get historical bhavcopy data for a symbol."""
        return self.bhavcopy.get_symbol_data(symbol, days=days)
```

---

## 📊 Example Analyses

### **1. Volume Trend Analysis**
```python
handler = BhavcopyHandler()
reliance = handler.get_symbol_data('RELIANCE', days=60)

# Volume trend
print(f"Avg Volume: {reliance['TTL_TRD_QNTY'].mean():.0f}")
print(f"Latest Volume: {reliance.iloc[0]['TTL_TRD_QNTY']:.0f}")
print(f"Vol Change: {((reliance.iloc[0]['TTL_TRD_QNTY'] / reliance['TTL_TRD_QNTY'].mean() - 1) * 100):.1f}%")
```

### **2. Sector Performance**
```python
df = handler.load_parquet()

# Group by sector (based on symbol patterns or SERIES)
sector_performance = df.groupby('SERIES').agg({
    'CLOSE_PRICE': 'mean',
    'TURNOVER_LACS': 'sum',
    'TTL_TRD_QNTY': 'mean'
}).round(2)
```

### **3. Volatility Analysis**
```python
nifty_50 = ['RELIANCE', 'TCS', 'INFY', 'ICICIBANK', ...]
volatility = {}

for symbol in nifty_50:
    df_sym = handler.get_symbol_data(symbol, days=30)
    daily_returns = df_sym['CLOSE_PRICE'].pct_change() * 100
    volatility[symbol] = daily_returns.std()

pd.Series(volatility).sort_values(ascending=False).head(10)
```

---

## ✅ Summary

**Use Parquet for:**
- ✅ Daily analysis scripts
- ✅ DataFrames that fit in memory (~100MB+)
- ✅ Balanced speed and storage
- ✅ Sharing with team (compressed)

**Use SQLite for:**
- ✅ Frequent symbol/date queries
- ✅ Complex filtering
- ✅ Data that's accessed rarely but needs fast lookups

**Keep CSV for:**
- ✅ Original source data (archive)
- ✅ Sharing with non-technical users
- ✅ Git version control (small files)

**Recommended Workflow:**
1. Keep CSVs in `data_bhavcopy/` (source)
2. Convert to Parquet daily (fast reads)
3. Optional: Also SQLite (for complex queries)
4. Archive old CSVs after 6+ months
