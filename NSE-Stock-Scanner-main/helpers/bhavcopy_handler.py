"""
Bhavcopy Data Handler
=====================
Efficiently load, store, and analyze NSE daily bhavcopy data.

Data Format:
- File: cm{date}bhav.csv (e.g., cm12Nov2025bhav.csv)
- Size: ~0.3-0.4 MB per day (~3000 rows)
- Columns: SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, 
           LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, 
           NO_OF_TRADES, DELIV_QTY, DELIV_PER

Storage Recommendations:
1. CSV (current): Good for small data, easy to access, slow for repeated reads
2. Parquet: Best balance - compressed, fast reads, preserves types
3. SQLite: Best for time-series queries, indexing
4. HDF5: Best for large historical data

This module implements all strategies for comparison.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BhavcopyHandler:
    """
    Efficiently manage NSE bhavcopy data with multiple storage backends.
    """
    
    def __init__(self, bhavcopy_dir='./data_bhavcopy', storage_format='parquet'):
        """
        Args:
            bhavcopy_dir: Directory containing bhavcopy CSV files
            storage_format: 'csv', 'parquet', 'sqlite', or 'hdf5'
        """
        self.bhavcopy_dir = Path(bhavcopy_dir)
        self.storage_format = storage_format
        self.parquet_dir = self.bhavcopy_dir / 'parquet'
        self.sqlite_path = self.bhavcopy_dir / 'bhavcopy.db'
        self.hdf5_path = self.bhavcopy_dir / 'bhavcopy.h5'
        
        # Ensure directories exist
        self.parquet_dir.mkdir(parents=True, exist_ok=True)
        
        # Column mappings and dtypes
        self.columns = {
            'SYMBOL': 'str',
            'SERIES': 'str',
            'DATE1': 'str',  # Will convert to datetime
            'PREV_CLOSE': 'float32',
            'OPEN_PRICE': 'float32',
            'HIGH_PRICE': 'float32',
            'LOW_PRICE': 'float32',
            'LAST_PRICE': 'float32',
            'CLOSE_PRICE': 'float32',
            'AVG_PRICE': 'float32',
            'TTL_TRD_QNTY': 'int32',
            'TURNOVER_LACS': 'float32',
            'NO_OF_TRADES': 'int32',
            'DELIV_QTY': 'int32',
            'DELIV_PER': 'float32',
        }

    def load_csv(self, date_str=None):
        """
        Load bhavcopy CSV file for a specific date.
        
        Args:
            date_str: Date string like '12Nov2025' or None for latest file
            
        Returns:
            pd.DataFrame with cleaned and typed data
        """
        if date_str is None:
            # Get the latest bhavcopy file
            csv_files = sorted(self.bhavcopy_dir.glob('cm*.csv'))
            if not csv_files:
                raise FileNotFoundError(f"No bhavcopy CSV files found in {self.bhavcopy_dir}")
            csv_file = csv_files[-1]
        else:
            csv_file = self.bhavcopy_dir / f'cm{date_str}bhav.csv'
            if not csv_file.exists():
                raise FileNotFoundError(f"File not found: {csv_file}")
        
        logger.info(f"Loading bhavcopy from: {csv_file}")
        
        # Read CSV with proper dtypes
        df = pd.read_csv(csv_file, dtype=self.columns)
        
        # Clean up whitespace in column names
        df.columns = df.columns.str.strip()
        
        # Convert DATE1 to datetime
        df['DATE'] = pd.to_datetime(df['DATE1'], format='%d-%b-%Y')
        df = df.drop('DATE1', axis=1)
        
        # Clean up whitespace in SYMBOL column
        df['SYMBOL'] = df['SYMBOL'].str.strip()
        
        logger.info(f"Loaded {len(df)} records from {csv_file.name}")
        return df

    def load_all_csvs(self, days=None):
        """
        Load all bhavcopy CSV files (or last N days).
        
        Args:
            days: Number of recent days to load (None = all files)
            
        Returns:
            pd.DataFrame with all bhavcopy data
        """
        csv_files = sorted(self.bhavcopy_dir.glob('cm*.csv'))
        
        if days:
            csv_files = csv_files[-days:]
        
        logger.info(f"Loading {len(csv_files)} bhavcopy files...")
        
        dfs = []
        for csv_file in csv_files:
            try:
                df = self.load_csv(csv_file.stem.replace('cm', '').replace('bhav', ''))
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Error loading {csv_file.name}: {e}")
        
        combined_df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded total {len(combined_df)} records from {len(dfs)} files")
        return combined_df

    # ==================== STORAGE BACKENDS ====================
    
    def save_parquet(self, df, date_str=None):
        """
        Save DataFrame to Parquet format (recommended for time-series).
        
        Benefits:
        - 70-80% compression (0.3MB CSV → 0.08MB Parquet)
        - Preserves dtypes and timezone info
        - Columnar storage - fast reads for specific columns
        - Supports partitioning by date
        - ~10x faster reads than CSV
        """
        if date_str is None:
            date_str = df['DATE'].max().strftime('%d%b%Y')
        
        parquet_file = self.parquet_dir / f'bhavcopy_{date_str}.parquet'
        df.to_parquet(parquet_file, compression='snappy', index=False)
        logger.info(f"Saved to Parquet: {parquet_file}")
        return parquet_file

    def load_parquet(self, date_str=None):
        """Load Parquet file for a specific date or latest."""
        if date_str is None:
            # Get latest parquet file
            parquet_files = sorted(self.parquet_dir.glob('*.parquet'))
            if not parquet_files:
                raise FileNotFoundError(f"No Parquet files in {self.parquet_dir}")
            parquet_file = parquet_files[-1]
        else:
            parquet_file = self.parquet_dir / f'bhavcopy_{date_str}.parquet'
        
        logger.info(f"Loading Parquet: {parquet_file.name}")
        return pd.read_parquet(parquet_file)

    def save_sqlite(self, df, if_exists='append'):
        """
        Save to SQLite (best for indexing and complex queries).
        
        Benefits:
        - Full SQL query capability
        - Fast symbol/date lookups with indexes
        - Supports transactions
        - Good for large historical data
        - Can be queried without loading entire dataset
        """
        import sqlite3
        
        conn = sqlite3.connect(self.sqlite_path)
        df.to_sql('bhavcopy', conn, if_exists=if_exists, index=False)
        
        # Create indexes for fast queries
        with conn:
            conn.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON bhavcopy(SYMBOL)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_date ON bhavcopy(DATE)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_series ON bhavcopy(SERIES)')
        
        conn.close()
        logger.info(f"Saved to SQLite: {self.sqlite_path}")

    def load_sqlite_query(self, query):
        """
        Load data using SQL query (efficient for large datasets).
        
        Examples:
            # Get specific symbol
            df = handler.load_sqlite_query(
                "SELECT * FROM bhavcopy WHERE SYMBOL='RELIANCE' ORDER BY DATE DESC"
            )
            
            # Get date range
            df = handler.load_sqlite_query(
                "SELECT * FROM bhavcopy WHERE DATE BETWEEN '2025-11-01' AND '2025-11-12'"
            )
            
            # Aggregated query
            df = handler.load_sqlite_query(
                "SELECT SYMBOL, AVG(CLOSE_PRICE) as avg_close, MAX(HIGH_PRICE) as high "
                "FROM bhavcopy WHERE SERIES='EQ' GROUP BY SYMBOL"
            )
        """
        import sqlite3
        
        conn = sqlite3.connect(self.sqlite_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df

    def save_hdf5(self, df, key='bhavcopy'):
        """
        Save to HDF5 (best for very large historical datasets).
        
        Benefits:
        - Excellent for big data (100GB+)
        - Fast hierarchical access
        - Supports compression
        - Good for time-series data
        
        Requires: pip install tables
        """
        try:
            df.to_hdf(self.hdf5_path, key, mode='a', complevel=9, complib='blosc')
            logger.info(f"Saved to HDF5: {self.hdf5_path}")
        except ImportError:
            logger.warning("HDF5 requires 'tables' package. Install with: pip install tables")

    # ==================== ANALYSIS FUNCTIONS ====================
    
    def get_symbol_data(self, symbol, days=None, storage='parquet'):
        """
        Get historical data for a specific symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE', 'TCS')
            days: Number of recent days to fetch (None = all)
            storage: 'csv', 'parquet', or 'sqlite'
        """
        if storage == 'sqlite':
            query = f"SELECT * FROM bhavcopy WHERE SYMBOL='{symbol.upper()}' ORDER BY DATE DESC"
            df = self.load_sqlite_query(query)
        elif storage == 'parquet':
            # Load all parquets and filter (more efficient for many symbols)
            parquet_files = sorted(self.parquet_dir.glob('*.parquet'), reverse=True)
            if days:
                parquet_files = parquet_files[:days]
            
            dfs = [pd.read_parquet(f) for f in parquet_files]
            df = pd.concat(dfs, ignore_index=True)
            df = df[df['SYMBOL'].str.upper() == symbol.upper()]
        else:  # csv
            df = self.load_all_csvs(days=days)
            df = df[df['SYMBOL'].str.upper() == symbol.upper()]
        
        return df.sort_values('DATE', ascending=False)

    def get_top_gainers(self, date_str=None, top_n=10):
        """Get top gainers for a specific date."""
        df = self.load_parquet(date_str) if Path(self.parquet_dir).exists() else self.load_csv(date_str)
        
        # Calculate daily change
        df['CHANGE_PCT'] = ((df['CLOSE_PRICE'] - df['PREV_CLOSE']) / df['PREV_CLOSE'] * 100).round(2)
        
        return df.nlargest(top_n, 'CHANGE_PCT')[
            ['SYMBOL', 'PREV_CLOSE', 'CLOSE_PRICE', 'CHANGE_PCT', 'TURNOVER_LACS']
        ]

    def get_top_losers(self, date_str=None, top_n=10):
        """Get top losers for a specific date."""
        df = self.load_parquet(date_str) if Path(self.parquet_dir).exists() else self.load_csv(date_str)
        
        df['CHANGE_PCT'] = ((df['CLOSE_PRICE'] - df['PREV_CLOSE']) / df['PREV_CLOSE'] * 100).round(2)
        
        return df.nsmallest(top_n, 'CHANGE_PCT')[
            ['SYMBOL', 'PREV_CLOSE', 'CLOSE_PRICE', 'CHANGE_PCT', 'TURNOVER_LACS']
        ]

    def get_volume_analysis(self, symbol, days=30):
        """Get volume analysis for a symbol over N days."""
        df = self.get_symbol_data(symbol, days=days)
        
        return {
            'symbol': symbol,
            'avg_volume': df['TTL_TRD_QNTY'].mean(),
            'avg_turnover': df['TURNOVER_LACS'].mean(),
            'avg_trades': df['NO_OF_TRADES'].mean(),
            'avg_delivery_pct': df['DELIV_PER'].mean(),
            'price_range': f"{df['LOW_PRICE'].min():.2f} - {df['HIGH_PRICE'].max():.2f}",
        }

    def export_to_csv(self, df, filename):
        """Export DataFrame to CSV for sharing."""
        output_path = self.bhavcopy_dir / filename
        df.to_csv(output_path, index=False)
        logger.info(f"Exported to: {output_path}")


# ==================== RECOMMENDED WORKFLOW ====================

def setup_bhavcopy_storage():
    """
    One-time setup: Convert all CSVs to Parquet for faster access.
    """
    handler = BhavcopyHandler(storage_format='parquet')
    
    logger.info("Converting all CSV files to Parquet format...")
    df_all = handler.load_all_csvs()
    
    # Save by date for better organization
    for date in df_all['DATE'].unique():
        df_date = df_all[df_all['DATE'] == date]
        handler.save_parquet(df_date, date.strftime('%d%b%Y'))
    
    logger.info("✅ Parquet setup complete!")
    
    # Also save to SQLite for efficient queries
    logger.info("Setting up SQLite for efficient queries...")
    handler.save_sqlite(df_all, if_exists='replace')
    logger.info("✅ SQLite setup complete!")


if __name__ == "__main__":
    # Example usage
    handler = BhavcopyHandler()
    
    # Load latest bhavcopy
    df = handler.load_csv()
    print(df.head())
    
    # Get top gainers
    print("\n=== Top 10 Gainers ===")
    print(handler.get_top_gainers())
    
    # Get top losers
    print("\n=== Top 10 Losers ===")
    print(handler.get_top_losers())
