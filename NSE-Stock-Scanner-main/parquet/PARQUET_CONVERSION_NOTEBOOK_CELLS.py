# Notebook cells for batch Parquet conversion
# Copy these cells into Tutorial.ipynb after the initialization section

# ============================================================================
# CELL 1: Install required package (if not already installed)
# ============================================================================

import subprocess
import sys

# Check if pyarrow is installed, if not install it
try:
    import pyarrow
    print("✅ PyArrow already installed")
except ImportError:
    print("⚠️ Installing PyArrow for Parquet support...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyarrow", "-q"])
    print("✅ PyArrow installed successfully")


# ============================================================================
# CELL 2: Batch conversion function
# ============================================================================

import pandas as pd
import numpy as np
from pathlib import Path
import time

def convert_bhavcopy_to_parquet(csv_path, verbose=False):
    """Convert single bhavcopy CSV to Parquet."""
    csv_path = Path(csv_path)
    
    # Define dtypes for efficient storage
    dtypes = {
        'SYMBOL': 'string',
        'SERIES': 'category',
        'OPEN_PRICE': 'float32',
        'HIGH_PRICE': 'float32',
        'LOW_PRICE': 'float32',
        'CLOSE_PRICE': 'float32',
        'LAST_PRICE': 'float32',
        'PREV_CLOSE': 'float32',
        'TTL_TRD_QNTY': 'int32',
        'TTL_TRD_VAL': 'float32',
        'TURNOVER_LACS': 'float32',
        'ISIN_CODE': 'string',
    }
    
    # Load CSV with optimized dtypes
    df = pd.read_csv(csv_path, dtype=dtypes)
    if 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE'], format='%d-%b-%Y', errors='coerce')
    
    # Save as Parquet
    parquet_path = csv_path.with_suffix('.parquet')
    df.to_parquet(parquet_path, engine='pyarrow', compression='snappy', index=False)
    
    if verbose:
        csv_size = csv_path.stat().st_size / 1024 / 1024
        parquet_size = parquet_path.stat().st_size / 1024 / 1024
        compression = (1 - parquet_size / csv_size) * 100
        print(f"✅ {csv_path.name}: {csv_size:.2f} MB → {parquet_size:.2f} MB ({compression:.0f}% compression)")
    
    return parquet_path

def batch_convert_all_bhavcopy(data_dir='./data_bhavcopy', show_progress=True):
    """Convert all CSV files to Parquet."""
    data_dir = Path(data_dir)
    csv_files = sorted(data_dir.glob('cm*.csv'))
    
    print(f"\n🔄 Converting {len(csv_files)} bhavcopy files to Parquet format")
    print(f"{'='*70}\n")
    
    start_time = time.time()
    total_csv = 0
    total_parquet = 0
    
    for i, csv_file in enumerate(csv_files, 1):
        try:
            parquet_file = convert_bhavcopy_to_parquet(csv_file, verbose=True)
            
            total_csv += csv_file.stat().st_size
            total_parquet += parquet_file.stat().st_size
            
            # Show progress every 50 files
            if show_progress and i % 50 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed
                remaining = (len(csv_files) - i) / rate
                print(f"\n⏱️ Progress: {i}/{len(csv_files)} | Speed: {rate:.1f} files/min | ETA: {remaining/60:.1f} min\n")
        
        except Exception as e:
            print(f"❌ Error converting {csv_file.name}: {e}")
    
    elapsed = time.time() - start_time
    compression_ratio = (1 - total_parquet / total_csv) * 100
    
    print(f"\n{'='*70}")
    print(f"✅ CONVERSION COMPLETE")
    print(f"{'='*70}")
    print(f"Files converted: {len(csv_files)}")
    print(f"Total CSV size:     {total_csv/1024/1024:.2f} MB")
    print(f"Total Parquet size: {total_parquet/1024/1024:.2f} MB")
    print(f"Space saved:        {(total_csv-total_parquet)/1024/1024:.2f} MB ({compression_ratio:.0f}%)")
    print(f"Time taken:         {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print(f"{'='*70}\n")
    
    return len(csv_files)


# ============================================================================
# CELL 3: Run the batch conversion
# ============================================================================

# ⚠️ WARNING: This will process ~850 files and take several minutes
# Make sure you have enough disk space and don't interrupt the process

converted = batch_convert_all_bhavcopy(data_dir='./data_bhavcopy', show_progress=True)
print(f"\n✅ Successfully converted {converted} files!")


# ============================================================================
# CELL 4: Verify conversion and list files
# ============================================================================

from pathlib import Path

data_dir = Path('./data_bhavcopy')

csv_files = sorted(data_dir.glob('cm*.csv'))
parquet_files = sorted(data_dir.glob('cm*.parquet'))

print(f"\n📊 Conversion Status")
print(f"{'='*70}")
print(f"CSV files remaining:     {len(csv_files)}")
print(f"Parquet files created:   {len(parquet_files)}")
print(f"Total bhavcopy files:    {len(csv_files) + len(parquet_files)}")
print(f"Conversion progress:     {len(parquet_files)/(len(csv_files) + len(parquet_files))*100:.1f}%")
print(f"{'='*70}\n")

# Show sample Parquet files
if parquet_files:
    print(f"✅ Parquet files created:")
    for pf in parquet_files[-10:]:  # Show last 10 files
        size_mb = pf.stat().st_size / 1024 / 1024
        df_sample = pd.read_parquet(pf)
        print(f"   {pf.name}")
        print(f"      Size: {size_mb:.2f} MB | Rows: {len(df_sample):,} | Columns: {len(df_sample.columns)}")


# ============================================================================
# CELL 5: Load and test Parquet file
# ============================================================================

from pathlib import Path

# Load latest Parquet file
data_dir = Path('./data_bhavcopy')
parquet_files = sorted(data_dir.glob('cm*.parquet'))

if parquet_files:
    latest_parquet = parquet_files[-1]
    print(f"📖 Loading {latest_parquet.name}...")
    
    df = pd.read_parquet(latest_parquet)
    
    print(f"\n✅ Loaded successfully!")
    print(f"   Shape: {df.shape}")
    print(f"   Columns: {list(df.columns)}")
    print(f"   Date: {df['DATE'].iloc[0] if 'DATE' in df.columns else 'N/A'}")
    print(f"\n📊 Sample data:")
    print(df.head())
    
    # Show data types (compressed)
    print(f"\n📐 Data types (memory optimized):")
    print(df.dtypes)
else:
    print("❌ No Parquet files found. Run the conversion cell first.")


# ============================================================================
# CELL 6: Load multiple Parquet files and aggregate
# ============================================================================

from pathlib import Path
import pandas as pd

data_dir = Path('./data_bhavcopy')
parquet_files = sorted(data_dir.glob('cm*.parquet'))

print(f"📚 Loading {len(parquet_files)} Parquet files...")

# Load multiple files
dfs = []
for pf in parquet_files[-30:]:  # Last 30 days
    df = pd.read_parquet(pf)
    dfs.append(df)
    print(f"   ✓ {pf.name} ({len(df):,} rows)")

# Combine all
df_combined = pd.concat(dfs, ignore_index=True)

print(f"\n✅ Combined {len(parquet_files)} files:")
print(f"   Total rows: {len(df_combined):,}")
print(f"   Date range: {df_combined['DATE'].min()} to {df_combined['DATE'].max()}")
print(f"   Unique symbols: {df_combined['SYMBOL'].nunique()}")

# Example: Get RELIANCE data across all dates
reliance = df_combined[df_combined['SYMBOL'] == 'RELIANCE'].sort_values('DATE')
print(f"\n📈 RELIANCE across {len(reliance)} days:")
print(reliance[['DATE', 'OPEN_PRICE', 'HIGH_PRICE', 'LOW_PRICE', 'CLOSE_PRICE', 'TTL_TRD_QNTY']])


# ============================================================================
# CELL 7: Delete original CSV files (AFTER verification!)
# ============================================================================

# ⚠️ WARNING: Only run this after verifying Parquet files work correctly!
# This will DELETE all original CSV files

from pathlib import Path
import shutil

data_dir = Path('./data_bhavcopy')
csv_files = sorted(data_dir.glob('cm*.csv'))

print(f"\n⚠️  WARNING: This will DELETE {len(csv_files)} CSV files!")
print(f"Space that will be freed: {sum(f.stat().st_size for f in csv_files) / 1024 / 1024:.2f} MB")
print(f"\n✅ Make sure Parquet files are working before running this!")

# To delete, uncomment the lines below:
# for csv_file in csv_files:
#     csv_file.unlink()
#     print(f"   Deleted {csv_file.name}")
# print(f"\n✅ Deleted all {len(csv_files)} CSV files!")

print("\n💡 When ready to delete, uncomment the delete code above.")
