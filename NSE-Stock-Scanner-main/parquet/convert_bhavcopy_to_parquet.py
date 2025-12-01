#!/usr/bin/env python3
"""
Batch convert all bhavcopy CSV files to Parquet format.
This script will process ~850 files and reduce disk space by ~77%.

Usage:
    python convert_bhavcopy_to_parquet.py
    
Progress:
    - Shows file count, compression ratio, and time elapsed
    - Saves in place: cm12Nov2025bhav.csv → cm12Nov2025bhav.parquet
    - Original CSVs kept as backup (can be deleted after verification)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import time
from datetime import datetime
import os

def get_csv_dtype_mapping():
    """Define optimal dtypes for bhavcopy columns to reduce memory usage."""
    return {
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
        'SYMBOL_NOTES': 'category',
        'FILLER': 'category',
        'DATE': 'string',  # Will convert to datetime after loading
    }

def load_bhavcopy_csv(csv_file):
    """Load CSV with optimized dtypes."""
    try:
        dtype_map = get_csv_dtype_mapping()
        df = pd.read_csv(csv_file, dtype=dtype_map)
        
        # Convert DATE to datetime
        if 'DATE' in df.columns:
            df['DATE'] = pd.to_datetime(df['DATE'], format='%d-%b-%Y', errors='coerce')
        
        return df
    except Exception as e:
        print(f"  ❌ Error loading {csv_file.name}: {e}")
        return None

def convert_csv_to_parquet(csv_file, output_dir=None, keep_csv=True, verbose=True):
    """
    Convert a single CSV file to Parquet format.
    
    Parameters:
    -----------
    csv_file : Path
        Path to CSV file
    output_dir : Path, optional
        Output directory for Parquet file (default: same as CSV)
    keep_csv : bool
        Keep original CSV file (default: True)
    verbose : bool
        Print conversion details (default: True)
    
    Returns:
    --------
    dict : {'csv_size': int, 'parquet_size': int, 'compression': float, 'rows': int}
    """
    csv_file = Path(csv_file)
    
    if not csv_file.exists():
        return None
    
    # Load CSV with optimized dtypes
    df = load_bhavcopy_csv(csv_file)
    if df is None:
        return None
    
    # Define output path
    if output_dir is None:
        output_dir = csv_file.parent
    else:
        output_dir = Path(output_dir)
    
    parquet_file = output_dir / csv_file.stem.replace('.csv', '') / f"{csv_file.stem}.parquet"
    parquet_file = output_dir / f"{csv_file.stem}.parquet"  # Simpler: same directory
    
    # Get file sizes
    csv_size = csv_file.stat().st_size
    
    # Save to Parquet with compression
    try:
        df.to_parquet(
            parquet_file,
            engine='pyarrow',
            compression='snappy',  # ~77% compression, fast
            index=False
        )
        parquet_size = parquet_file.stat().st_size
        compression_ratio = (1 - parquet_size / csv_size) * 100
        
        if verbose:
            print(f"  ✅ {csv_file.name}")
            print(f"     CSV: {csv_size/1024/1024:.2f} MB → Parquet: {parquet_size/1024/1024:.2f} MB ({compression_ratio:.0f}% reduction)")
            print(f"     Rows: {len(df):,}, Columns: {len(df.columns)}")
        
        return {
            'csv_size': csv_size,
            'parquet_size': parquet_size,
            'compression': compression_ratio,
            'rows': len(df),
            'status': 'success'
        }
    
    except Exception as e:
        print(f"  ❌ Error saving {parquet_file}: {e}")
        return {'status': 'error', 'error': str(e)}

def batch_convert_bhavcopy(data_dir='./data_bhavcopy', keep_csv=True, limit=None):
    """
    Convert all bhavcopy CSV files to Parquet format.
    
    Parameters:
    -----------
    data_dir : str or Path
        Directory containing CSV files (default: './data_bhavcopy')
    keep_csv : bool
        Keep original CSV files (default: True)
    limit : int, optional
        Process only first N files (default: None = all files)
    
    Returns:
    --------
    dict : Summary statistics
    """
    data_dir = Path(data_dir)
    
    if not data_dir.exists():
        print(f"❌ Directory not found: {data_dir}")
        return None
    
    # Find all CSV files
    csv_files = sorted(data_dir.glob('cm*.csv'))  # bhavcopy files start with 'cm'
    
    if not csv_files:
        print(f"⚠️ No CSV files found in {data_dir}")
        return None
    
    if limit:
        csv_files = csv_files[:limit]
    
    print(f"\n{'='*70}")
    print(f"🔄 Converting {len(csv_files)} bhavcopy files to Parquet format")
    print(f"📁 Source: {data_dir}")
    print(f"💾 Keep originals: {'Yes' if keep_csv else 'No'}")
    print(f"{'='*70}\n")
    
    start_time = time.time()
    stats = {
        'total_files': len(csv_files),
        'success': 0,
        'failed': 0,
        'total_csv_size': 0,
        'total_parquet_size': 0,
        'total_rows': 0,
        'files': []
    }
    
    for i, csv_file in enumerate(csv_files, 1):
        print(f"\n[{i}/{len(csv_files)}]", end='')
        
        result = convert_csv_to_parquet(
            csv_file,
            output_dir=data_dir,
            keep_csv=keep_csv,
            verbose=True
        )
        
        if result and result.get('status') == 'success':
            stats['success'] += 1
            stats['total_csv_size'] += result['csv_size']
            stats['total_parquet_size'] += result['parquet_size']
            stats['total_rows'] += result['rows']
            stats['files'].append({
                'name': csv_file.name,
                'csv_size': result['csv_size'],
                'parquet_size': result['parquet_size']
            })
        else:
            stats['failed'] += 1
        
        # Progress indicator every 10 files
        if i % 10 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            remaining = (len(csv_files) - i) / rate if rate > 0 else 0
            print(f"\n   ⏱️ Progress: {i}/{len(csv_files)} files | "
                  f"Speed: {rate:.1f} files/min | "
                  f"ETA: {remaining/60:.1f} minutes")
    
    # Final summary
    elapsed = time.time() - start_time
    total_csv_mb = stats['total_csv_size'] / 1024 / 1024
    total_parquet_mb = stats['total_parquet_size'] / 1024 / 1024
    overall_compression = (1 - stats['total_parquet_size'] / stats['total_csv_size']) * 100 if stats['total_csv_size'] > 0 else 0
    
    print(f"\n{'='*70}")
    print(f"✅ CONVERSION COMPLETE")
    print(f"{'='*70}")
    print(f"Successful: {stats['success']}/{stats['total_files']} files")
    print(f"Failed: {stats['failed']}/{stats['total_files']} files")
    print(f"\n📊 Storage Savings:")
    print(f"   Original Size:  {total_csv_mb:>10.2f} MB")
    print(f"   Parquet Size:   {total_parquet_mb:>10.2f} MB")
    print(f"   Space Saved:    {total_csv_mb - total_parquet_mb:>10.2f} MB ({overall_compression:.0f}%)")
    print(f"\n📈 Data Statistics:")
    print(f"   Total Rows:     {stats['total_rows']:>10,}")
    print(f"   Total Files:    {stats['success']:>10}")
    print(f"   Avg Rows/File:  {stats['total_rows'] / stats['success'] if stats['success'] > 0 else 0:>10,.0f}")
    print(f"\n⏱️ Performance:")
    print(f"   Total Time:     {elapsed:>10.1f} seconds")
    print(f"   Avg Time/File:  {elapsed / stats['success'] if stats['success'] > 0 else 0:>10.2f} seconds")
    print(f"{'='*70}\n")
    
    return stats

def list_conversion_status(data_dir='./data_bhavcopy'):
    """Show which files are converted to Parquet vs still CSV."""
    data_dir = Path(data_dir)
    
    csv_files = sorted(data_dir.glob('cm*.csv'))
    parquet_files = sorted(data_dir.glob('cm*.parquet'))
    
    print(f"\n📂 Conversion Status")
    print(f"{'='*70}")
    print(f"CSV files remaining:     {len(csv_files)}")
    print(f"Parquet files created:   {len(parquet_files)}")
    print(f"Total bhavcopy files:    {len(csv_files) + len(parquet_files)}")
    print(f"Conversion progress:     {len(parquet_files)/(len(csv_files) + len(parquet_files))*100:.1f}%")
    print(f"{'='*70}\n")
    
    if parquet_files:
        print(f"✅ Sample Parquet files created:")
        for pf in parquet_files[:5]:
            size_mb = pf.stat().st_size / 1024 / 1024
            print(f"   - {pf.name} ({size_mb:.2f} MB)")
        if len(parquet_files) > 5:
            print(f"   ... and {len(parquet_files) - 5} more")

if __name__ == "__main__":
    # Convert all CSV files to Parquet
    stats = batch_convert_bhavcopy(
        data_dir='./data_bhavcopy',
        keep_csv=True,
        limit=None  # Set to test number like 5, 10, 50
    )
    
    # Show status
    if stats:
        list_conversion_status()
        
        # Optional: Delete original CSVs after verification
        print("\n💡 NEXT STEPS:")
        print("1. Verify conversion was successful by checking the summary above")
        print("2. Test loading Parquet files in Tutorial.ipynb")
        print("3. Once confirmed working, delete original CSV files:")
        print("   python -c \"import shutil; shutil.rmtree('./data_bhavcopy/*.csv')\"")
