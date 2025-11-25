from jugaad_data.nse import stock_df
from .nse_data import NSEData
from jugaad_data.nse import bhavcopy_save

from datetime import date, datetime, timedelta

import pandas as pd
import numpy as np

from os import listdir, mkdir, cpu_count
from glob import glob
from shutil import rmtree
import os
from os.path import join, expanduser

import json
import warnings
import logging

import random

from multiprocessing import Pool
import tempfile

NSE = NSEData()
from os import remove
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

workers = int(0.8*cpu_count())


drop = ['SERIES','PREV. CLOSE','VWAP','VOLUME','VALUE','NO OF TRADES', 'LTP']


class DataHandler:
    def __init__(self, data_path = './data', check_fresh = False, bhavcopy_path = './data_bhavcopy'):
        '''
        '''
        self.present = date.today()
        self.week_num = self.present.strftime("%W")
        
        self.data_path = data_path
        self.bhavcopy_path = bhavcopy_path

        self.read_data = DataHandler.read_data # because it is static
        self.data = self.read_data()
        self.all_stocks = self.data['all_stocks']
        
        if check_fresh:
            print('Checking Fresh Data.....')
            self.__fresh()
            self.check_new_data_availability()
            # self.prune_unregistered_stocks()

    
    def update_FnO(self):
        '''
        Update the newest Futures and Options Derivatives list
        '''
        r = NSE.get_live_nse_data('https://www1.nseindia.com/content/fo/fo_underlyinglist.htm')
        df = pd.read_html(r.text)[3].iloc[5:]
        self.data['f&o'] = df.iloc[:,1].values.tolist()
        self.update_data(self.data)
             

    def update_new_listings(self):
        '''
        Update new IPO or stocks as they are listed on the NSE and remove the ones which have been removed from the listings
        '''
        print('\nUpdating New Listings.....')
        old = set(self.data['registered_stocks'])
        df = pd.read_csv("https://archives.nseindia.com/content/equities/EQUITY_L.csv")
        df = df[df[' SERIES'] == 'EQ'].copy()
        # Clean up column names that might have leading spaces
        df.columns = df.columns.str.strip()
        new_symbols = set(df['SYMBOL'].values.tolist())

        to_update = new_symbols - old

        if not to_update:
            logging.info("No new listings found.")
            return

        new_listings_df = df[df['SYMBOL'].isin(to_update)]

        for index in new_listings_df.index:
            try:
                symbol = new_listings_df.loc[index, "SYMBOL"]
                company_name = new_listings_df.loc[index, "NAME OF COMPANY"]
                
                # Add to registry and create filename mapping BEFORE downloading
                self.data['registered_stocks'].append(symbol)
                self.data['all_stocks'][symbol] = f'{symbol}_{company_name}.csv'
                self.update_data(self.data) # Persist the new mapping immediately
                
                logging.info(f"Found new listing: {symbol}. Downloading...")
                self.download_new(symbol)
            except Exception as e:
                logging.error(f"Error processing new listing {new_listings_df.loc[index, 'SYMBOL']}: {e}")

        print('\nUpdate of new listings successful.')

    
    def update_fresh_nifty_indices(self):
        '''
        Update all the new Nifty Indices as they might have changed or altered. Good to call it once in a while
        '''
        print('Updating New Nifty, Sectoral and thematic Indices')
        success = True
        try:
            for index_name in ['Sectoral Indices','Thematic Indices']: # Update Sectoral first
                index_key = index_name.replace(' ','_').lower() # setoral_indices, thematic_indices
                self.data[index_key] = {} # Will contain names of individual sectors

                branches = self.data['all_indices_names'][index_name] # Get all the available sectors and themes
                for branch_name in branches: # get individial names: Such as Nifty IT, Nifty Auto etc
                    names = NSE.open_nse_index(branch_name, show_n=9999)['symbol'].tolist()
                    self.data[index_key][branch_name] = names

            nifties = {'nifty_50':'NIFTY 50', 'nifty_100': 'NIFTY 100', 'nifty_200':'NIFTY 200', 'nifty_500':'NIFTY500 MULTICAP 50:25:25'}
            for index_name in nifties.keys():
                valid_names = [] # Names which are in Nifty Index but not in registered

                names = NSE.open_nse_index(nifties[index_name], show_n=500)['symbol'].tolist()
                for name in names:
                    if name in self.data['registered_stocks']:
                        valid_names.append(name)
                self.data[index_name] = valid_names

        except Exception as e:
            success = False
            warnings.warn(f"ERROR Occured: {e}\nTry again later")
            
        if success:
            print('Successful!')
            self.update_data(self.data)
        

    def __fresh(self,):
        files = listdir(self.data_path)
        if not len(files):
            warnings.warn(f"No CSV data files present at {self.data_path} Downloading new data for analysis")
            self.multiprocess_download_stocks(stocks=list(self.data['registered_stocks']))
            
            self.update_fresh_files()
  
    
    @staticmethod
    def read_data(path = './', file = 'data.json'):
        '''
        Write the data in json file
        args:
            path: Path of the directory
            File: Json Filename
        '''
        with open(join(path,file)) as f:
            return json.load(f)


    def update_data(self, updated_data:dict, path:str = './', file:str = 'data.json'):
        '''
        Update the data in the json file
        args:
            updated_data: Dictonary you want to update
            path: Path of the directory
            File: Json Filename
        '''
        with open(join(path,file), 'w') as f:
            json.dump(updated_data,f)

    
    def open_live_stock_data(self, name:str, from_date=None):
        '''
        Open the fresh stock from the market
        args:
            name: ID of the stock given
            from_date: Date from which to fetch the data. Defaults to 750 days ago.
        '''
        if from_date is None:
            from_date = self.present - timedelta(days=750) # almost 2 years
        return stock_df(symbol=name, from_date=from_date, to_date=self.present, series="EQ").drop(drop, axis=1)
    
    
    def open_downloaded_stock(self, name:str, resample:str = None, kind = 'daily'):
        '''
        Open the Individual stock based on it's Official Term
        args:
            name: Name / ID given to the stock. Example, Infosys is "INFY"
            resample: Resample the data to Weekly, Monthly, Yearly. Pass in ['M','W','Y']. Default: None means Daily
            kind: Kind of data file to open" could be "daily" or any of [minutes_2, minutes_3, minutes_4, minutes_5, minutes_15, minutes_30, minutes_60]
        returns: DataFrame of that stock
        '''
        try:
            if name not in self.all_stocks:
                raise KeyError(f"Stock '{name}' not found in all_stocks mapping.")

            if kind == 'daily':
                df = pd.read_csv(join(self.data_path, self.all_stocks[name]))
            else:
                file = f'./intraday_data/{kind}/{self.all_stocks[name]}'
                df = pd.read_csv(file)

            df['DATE'] = pd.to_datetime(df['DATE'])
            if resample and kind == 'daily':
                df = self.resample_data(df, resample)
            return df
        except KeyError as e:
            logging.warning(f"Could not find stock '{name}' in mapping: {e}")
            return pd.DataFrame()
        except (FileNotFoundError, KeyError) as e:
            logging.warning(f"Could not open data file for stock '{name}' (kind: {kind}): {e}")
            return pd.DataFrame()

    
    def resample_data(self, data, to:str  = 'W', names:tuple = ('OPEN','CLOSE','LOW','HIGH','DATE')):
        '''
        Resample the data from Daily to Weekly, Monthly or Yearly
        args:
            data: Dataframe of Daily data
            to: One of  ['W','M','Y']
        '''
        Open, Close, Low, High, Date = names
        data = data.resample(to,on=Date).agg({Open:'first', High:'max', Low: 'min', Close:'last'})
        return data.sort_index(ascending = False).reset_index()
    

    def download_new(self, name:str):
        '''
        Download a New Stock Data
        args:
            name: ID / name of the Stock
         '''
        try: # This method now assumes the filename exists in all_stocks
            if name not in self.data['all_stocks']:
                raise KeyError(f"'{name}' not found in all_stocks. Cannot determine filename.")
            df = self.open_live_stock_data(name)
            df['DATE'] = pd.to_datetime(df['DATE'])
            filename = self.data['all_stocks'][name]
            save_path = join(self.data_path, filename)
            df.to_csv(save_path, index=None)
            logging.info(f"Successfully saved: {name} to {save_path}")
            return (name, True)
        except Exception as e:
            logging.error(f"Failed to download {name}: {e}")
            return (name, False)


    def multiprocess_download_stocks(self, stocks: list, batch_size: int = 100):
        '''
        Multiprocess Download stocks
        args:
            stocks: List of stocks to download
            batch_size: The number of stocks to process in each batch.
        '''
        # Ensure stocks is a list, not a dictionary
        if isinstance(stocks, dict):
            stocks = list(stocks.keys())

        total_stocks = len(stocks)
        logging.info(f"Starting download for {total_stocks} stocks in batches of {batch_size}.")

        for i in range(0, total_stocks, batch_size):
            batch = stocks[i:i + batch_size]
            logging.info(f"--- Processing batch {i//batch_size + 1}/{(total_stocks + batch_size - 1)//batch_size} ({len(batch)} stocks) ---")
            
            with Pool(processes=workers) as pool:
                results = pool.map(self.download_new, batch)
            
            successful_downloads = sum(1 for _, success in results if success)
            logging.info(f"--- Batch complete. Successfully downloaded {successful_downloads}/{len(batch)} stocks. ---")

        return True

    def update_stock_data(self, name: str):
        '''
        Appends new data to an existing stock file.
        args:
            name: ID / name of the Stock
        '''
        try:
            local_df = self.open_downloaded_stock(name)
            if local_df.empty:
                # If the local file is empty or doesn't exist, do a full download.
                return self.download_new(name)

            # Get the last date from the local file and fetch new data from the next day.
            last_date = pd.to_datetime(local_df['DATE'].iloc[0]).date()
            from_date = last_date + timedelta(days=1)

            # Only fetch if the last date is not today or in the future
            if from_date > self.present:
                logging.info(f"'{name}' is already up-to-date.")
                return (name, True)

            new_data_df = self.open_live_stock_data(name, from_date=from_date)

            if not new_data_df.empty:
                # Combine old and new data, remove duplicates, and sort
                combined_df = pd.concat([new_data_df, local_df]).drop_duplicates(subset=['DATE'], keep='first')
                combined_df['DATE'] = pd.to_datetime(combined_df['DATE'])
                combined_df.sort_values(by='DATE', ascending=False, inplace=True)
                
                # Save the updated dataframe
                save_path = join(self.data_path, self.all_stocks[name])
                combined_df.to_csv(save_path, index=None)
                logging.info(f"Successfully updated: {name}")
            else:
                logging.info(f"No new data to update for {name}.")
            
            return (name, True)

        except Exception as e:
            logging.error(f"Failed to update {name}: {e}")
            return (name, False)

    def multiprocess_update_stocks(self, stocks: list, batch_size: int = 100):
        '''
        Multiprocess update for a list of stocks.
        args:
            stocks: List of stocks to update.
            batch_size: The number of stocks to process in each batch.
        '''
        if isinstance(stocks, dict):
            stocks = list(stocks.keys())

        total_stocks = len(stocks)
        logging.info(f"Starting update for {total_stocks} stocks.")
        with Pool(processes=workers) as pool:
            results = pool.map(self.update_stock_data, stocks)
        successful_updates = sum(1 for _, success in results if success)
        logging.info(f"--- Update complete. Successfully updated {successful_updates}/{total_stocks} stocks. ---")
        return True

    def check_new_data_availability(self):
        '''
        Check and download new available or unfinished data
        '''
        stock_list_to_check = self.data.get('nifty_50')
        if not stock_list_to_check: # Fallback if nifty_50 is empty
            stock_list_to_check = self.data.get('registered_stocks', [])
        
        # Ensure the chosen stock exists in all_stocks to prevent KeyError
        valid_stocks_to_check = [s for s in stock_list_to_check if s in self.all_stocks]
        if not valid_stocks_to_check:
            return # Nothing to check if no valid stocks are found
        name = random.choice(valid_stocks_to_check)
        try:
            old = self.open_downloaded_stock(name)
            new = self.open_live_stock_data(name)
            if not new.empty and (old.empty or old.iloc[0,0] < new.iloc[0,0]):
                print('New daily data available. Updating all stocks...')
                self.multiprocess_update_stocks(stocks=list(self.data['registered_stocks']))
        except FileNotFoundError:
            print("Data file not found for {}. Downloading it.".format(name))
            self.download_new(name)

        
        missing_list = set(self.all_stocks.keys()) - {i.split('_')[0] for i in listdir(self.data_path)}
        if len(missing_list):
            print('Data Count Mismatch. Downloading Missing.....',missing_list)
            self.multiprocess_download_stocks(stocks=list(missing_list))
        
        self.update_fresh_files()
        

    def update_fresh_files(self):
        '''
        Update Downloaded Files in the data.json
        '''
        files = listdir(self.data_path)
        self.data = self.read_data()

        for file in files:
            # Handles filenames that may contain multiple underscores in the company name.
            # We only need the symbol, which is the first part.
            parts = file.split('_', 1) # Split only on the first underscore
            if len(parts) < 1 or not parts[0]:
                logging.warning(f"Skipping file with unexpected format: {file}")
                continue
            key = parts[0]
            self.data['all_stocks'][key] = file

        self.update_data(self.data)

    def prune_unregistered_stocks(self):
        '''
        Removes data files and JSON entries for stocks that are no longer in the 'registered_stocks' list.
        This acts as a cleanup utility to keep the data directory and the data.json file in sync.
        '''
        logging.info("Starting to prune unregistered stocks...")
        
        registered_stocks = set(self.data.get('registered_stocks', []))
        all_stocks_keys = set(self.all_stocks.keys())
        
        stocks_to_remove = all_stocks_keys - registered_stocks
        
        if not stocks_to_remove:
            logging.info("No unregistered stocks to prune. Files and JSON are in sync with registered_stocks.")
            return

        logging.info(f"Found {len(stocks_to_remove)} stocks to prune.")
        
        for stock_symbol in stocks_to_remove:
            # Get filename and remove from all_stocks dict in one go
            filename = self.data['all_stocks'].pop(stock_symbol, None)
            
            if filename:
                file_path = join(self.data_path, filename)
                try:
                    remove(file_path)
                    logging.info(f"Removed data file and JSON entry for unregistered stock: {stock_symbol}")
                except FileNotFoundError:
                    logging.warning(f"File not found for {stock_symbol}, but removed its entry from JSON.")
        
        self.update_data(self.data)
        logging.info("Pruning complete.")
    
    def download_bhavcopy(self, start_date: date = None, end_date: date = None, days: int = 7):
        '''
        Downloads historical Bhavcopy files from the NSE archives.

        Args:
            start_date (date, optional): The most recent date to start downloading from. 
                                         Defaults to today.
            end_date (date, optional): The oldest date to download to. 
                                       If not provided, it's calculated from `days`.
            days (int, optional): The number of days to download for, going backwards from 
                                  start_date. Used if end_date is not specified. Defaults to 7.
        '''
        bhavcopy_path = self.bhavcopy_path
        try:
            if not os.path.exists(bhavcopy_path):
                os.makedirs(bhavcopy_path)
                logging.info(f"Created directory: {bhavcopy_path}")
        except PermissionError:
            # Fallback to a user-writable directory if creating under bhavcopy_path fails
            fallback_base = join(expanduser('~'), 'NSE-Stock-Scanner-data')
            bhavcopy_path = join(fallback_base, 'bhavcopy')
            try:
                if not os.path.exists(bhavcopy_path):
                    os.makedirs(bhavcopy_path)
                logging.warning(f"Permission denied creating {self.bhavcopy_path}. Using fallback: {bhavcopy_path}")
            except PermissionError:
                # Last resort: use system temp directory
                bhavcopy_path = join(tempfile.gettempdir(), 'nse_bhavcopy')
                if not os.path.exists(bhavcopy_path):
                    os.makedirs(bhavcopy_path)
                logging.warning(f"Permission denied creating fallback directories. Using temp directory: {bhavcopy_path}")

        if not start_date:
            start_date = date.today()
        
        if not end_date:
            end_date = start_date - timedelta(days=days)

        logging.info(f"Starting Bhavcopy download from {end_date.strftime('%Y-%m-%d')} to {start_date.strftime('%Y-%m-%d')}")

        current_date = start_date
        while current_date >= end_date:
            try:
                bhavcopy_save(current_date, bhavcopy_path)
                logging.info(f"Successfully downloaded Bhavcopy for {current_date.strftime('%Y-%m-%d')}")
            except Exception as e:
                logging.warning(f"Could not download Bhavcopy for {current_date.strftime('%Y-%m-%d')}. It might be a holiday. Error: {e}")
            current_date -= timedelta(days=1)
        
        logging.info("Bhavcopy download process finished.")


    def update_stocks_with_bhavcopy_data(self, days: int = 7, bhav_files: list = None, dry_run: bool = False, symbols: list = None, compute_52w: bool = False, sort_descending: bool = True):
        """
        Read Bhavcopy CSV(s) from self.bhavcopy_path and append/update per-symbol files in self.data_path.

        Args:
            days: Number of latest bhavcopy files to use (when bhav_files is None).
            bhav_files: Optional explicit list of file paths to bhavcopy CSVs to process.
            dry_run: If True, don't write any files or update data.json; only print actions.
            symbols: Optional list of symbols to limit processing to (faster tests).
        """
        bhavcopy_path = self.bhavcopy_path
        data_path = self.data_path
        all_stocks = self.data.get('all_stocks', {})

        # Ensure paths exist
        try:
            if not os.path.exists(data_path):
                os.makedirs(data_path)
                logging.info(f"Created directory: {data_path}")
            if not os.path.exists(bhavcopy_path):
                os.makedirs(bhavcopy_path)
                logging.info(f"Created directory: {bhavcopy_path}")
        except PermissionError:
            fallback_base = join(expanduser('~'), 'NSE-Stock-Scanner-data')
            bhavcopy_path = join(fallback_base, 'bhavcopy')
            try:
                if not os.path.exists(bhavcopy_path):
                    os.makedirs(bhavcopy_path)
                logging.warning(f"Permission denied creating {self.bhavcopy_path}. Using fallback: {bhavcopy_path}")
            except PermissionError:
                bhavcopy_path = join(tempfile.gettempdir(), 'nse_bhavcopy')
                if not os.path.exists(bhavcopy_path):
                    os.makedirs(bhavcopy_path)
                logging.warning(f"Permission denied creating fallback directories. Using temp directory: {bhavcopy_path}")

        # Find list of files
        if bhav_files is None:
            pattern = join(bhavcopy_path, 'cm*bhav.csv')
            all_files = sorted(glob(pattern), key=os.path.getmtime, reverse=True)
            bhav_files = all_files[:days]

        if not bhav_files:
            logging.info('No Bhavcopy files found to process. Please download bhavcopy first or provide explicit file paths.')
            return False

        logging.info(f"Processing {len(bhav_files)} Bhavcopy files...")

        processed = 0
        unknown_symbols = set()
        created_files = 0
        updated_files = 0
        errors = []
        symbol_status = {}
        for bhav_file in bhav_files:
            logging.info(f"Reading bhavcopy: {bhav_file}")
            try:
                df_bhav = pd.read_csv(bhav_file, sep=None, engine='python', encoding='latin1', keep_default_na=True)
                df_bhav.columns = df_bhav.columns.str.strip().str.replace('\n', ' ').str.replace(' ', '_').str.upper()
            except Exception as e:
                logging.warning(f"Failed to read {bhav_file}: {e}")
                continue

            required_columns = ['SYMBOL', 'SERIES', 'DATE1']
            if not all(c in df_bhav.columns for c in required_columns):
                logging.warning(f"Skipping {bhav_file} - missing required columns. Found columns: {df_bhav.columns.tolist()[:10]}")
                continue

            eq_rows = df_bhav[df_bhav['SERIES'].astype(str).str.strip().str.upper() == 'EQ'].copy()
            if eq_rows.empty:
                logging.info(f"No EQ rows found in {bhav_file}. Skipping.")
                continue

            for idx, row in eq_rows.iterrows():
                symbol = str(row.get('SYMBOL', '')).strip().upper()
                if symbol == '':
                    continue
                if symbols and symbol not in symbols:
                    continue

                if symbol not in all_stocks:
                    unknown_symbols.add(symbol)
                    default_filename = f"{symbol}_EQ_{symbol}.csv"
                    all_stocks[symbol] = default_filename
                    if not dry_run:
                        self.data['all_stocks'][symbol] = default_filename

                filename = all_stocks.get(symbol)
                save_path = join(data_path, filename)

                def _try_cols(d, names):
                    for n in names:
                        if n in d.index:
                            return d[n]
                    return None

                date_val = _try_cols(row, ['DATE1', 'TRADE_DATE', 'DATE'])
                if pd.isnull(date_val):
                    try:
                        date_val = datetime.fromtimestamp(os.path.getmtime(bhav_file)).strftime('%Y-%m-%d')
                    except Exception:
                        date_val = pd.NaT

                try:
                    date_str = pd.to_datetime(date_val, dayfirst=False, errors='coerce')
                    if pd.isna(date_str):
                        date_str = pd.to_datetime(date_val, dayfirst=True, errors='coerce')
                except Exception:
                    date_str = pd.to_datetime(date_val, errors='coerce')
                if pd.isna(date_str):
                    date_s = str(date_val)
                else:
                    date_s = date_str.strftime('%Y-%m-%d')

                open_price = _try_cols(row, ['OPEN_PRICE', 'OPEN'])
                high_price = _try_cols(row, ['HIGH_PRICE', 'HIGH'])
                low_price = _try_cols(row, ['LOW_PRICE', 'LOW'])
                close_price = _try_cols(row, ['CLOSE_PRICE', 'CLOSE', 'LAST_PRICE'])
                if pd.isnull(close_price):
                    close_price = row.get('CLOSE_PRICE')

                def _safe_to_float(v):
                    try:
                        return float(v) if pd.notnull(v) and v != '' else np.nan
                    except Exception:
                        return np.nan

                open_price = _safe_to_float(open_price)
                high_price = _safe_to_float(high_price)
                low_price = _safe_to_float(low_price)
                close_price = _safe_to_float(close_price)

                new_row = {
                    'DATE': date_s,
                    'OPEN': open_price,
                    'HIGH': high_price,
                    'LOW': low_price,
                    'CLOSE': close_price,
                    '52W H': np.nan,
                    '52W L': np.nan,
                    'SYMBOL': symbol,
                }

                try:
                    # Ensure existing_df has the expected columns and avoid pd.concat with empty/all-NA DataFrames
                    expected_cols = ['DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', '52W H', '52W L', 'SYMBOL']
                    if os.path.exists(save_path):
                        try:
                            existing_df = pd.read_csv(save_path)
                            # Ensure all expected columns are present
                            for c in expected_cols:
                                if c not in existing_df.columns:
                                    existing_df[c] = np.nan
                            existing_df = existing_df[expected_cols]
                        except Exception as e:
                            logging.warning(f"Could not read existing file {save_path} - will create a new one. Error: {e}")
                            existing_df = pd.DataFrame(columns=expected_cols)
                    else:
                        existing_df = pd.DataFrame(columns=expected_cols)
                except Exception as e:
                    logging.warning(f"Error handling file {save_path}: {e}")
                    continue

                if not existing_df.empty and 'DATE' in existing_df.columns:
                    try:
                        existing_df['DATE'] = pd.to_datetime(existing_df['DATE'], errors='coerce').dt.strftime('%Y-%m-%d')
                    except Exception:
                        pass

                new_date_val = new_row['DATE']
                duplicate = False
                if (not existing_df.empty) and ('DATE' in existing_df.columns):
                    duplicate = (existing_df['DATE'] == new_date_val).any()

                if duplicate:
                    try:
                        if not dry_run:
                            existing_df.loc[existing_df['DATE'] == new_date_val, ['OPEN', 'HIGH', 'LOW', 'CLOSE']] = [new_row['OPEN'], new_row['HIGH'], new_row['LOW'], new_row['CLOSE']]
                            # If compute_52w is requested, recompute 52-week H/L using the full combined series
                            try:
                                if compute_52w and not existing_df.empty:
                                    tmp = existing_df.copy()
                                    tmp['DATE'] = pd.to_datetime(tmp['DATE'], errors='coerce')
                                    tmp['HIGH'] = pd.to_numeric(tmp['HIGH'], errors='coerce')
                                    tmp['LOW'] = pd.to_numeric(tmp['LOW'], errors='coerce')
                                    tmp.sort_values('DATE', inplace=True)
                                    tmp['52W H'] = tmp['HIGH'].rolling(window=252, min_periods=1).max()
                                    tmp['52W L'] = tmp['LOW'].rolling(window=252, min_periods=1).min()
                                    # sort before writing
                                    if sort_descending:
                                        tmp = tmp.sort_values('DATE', ascending=False)
                                    else:
                                        tmp = tmp.sort_values('DATE', ascending=True)
                                    existing_df = tmp
                            except Exception as e:
                                logging.warning(f"Failed to compute 52W values for duplicate symbol {symbol}: {e}")
                            # Always ensure consistent DATE string formatting and ordering before write
                            try:
                                if 'DATE' in existing_df.columns:
                                    existing_df['DATE'] = pd.to_datetime(existing_df['DATE'], errors='coerce').dt.strftime('%Y-%m-%d')
                            except Exception:
                                pass
                            if sort_descending and 'DATE' in existing_df.columns:
                                existing_df = existing_df.sort_values('DATE', ascending=False)
                            elif 'DATE' in existing_df.columns:
                                existing_df = existing_df.sort_values('DATE', ascending=True)
                            existing_df.to_csv(save_path, index=False)
                            updated_files += 1
                            # mark per-symbol status
                            sstatus = symbol_status.setdefault(symbol, {'created': False, 'updated': 0, 'rows_processed': 0, 'error': None})
                            sstatus['updated'] += 1
                    except Exception as e:
                        errors.append({'symbol': symbol, 'error': str(e), 'path': save_path})
                else:
                    new_df = pd.DataFrame([new_row], columns=existing_df.columns if not existing_df.empty else ['DATE','OPEN','HIGH','LOW','CLOSE','52W H','52W L','SYMBOL'])
                    try:
                        if existing_df.empty:
                            combined = new_df
                        else:
                            combined = pd.concat([new_df, existing_df], ignore_index=True, sort=False)
                        combined['DATE'] = pd.to_datetime(combined['DATE'], errors='coerce')
                        combined['DATE'] = combined['DATE'].dt.strftime('%Y-%m-%d')
                        combined.drop_duplicates(subset=['DATE'], keep='first', inplace=True)
                        # Clean up column ordering
                        combined = combined[['DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', '52W H', '52W L', 'SYMBOL']].copy()
                        if not dry_run:
                            # Optionally compute 52-week High/Low across the combined series
                            if compute_52w and not combined.empty:
                                try:
                                    tmp = combined.copy()
                                    tmp['DATE'] = pd.to_datetime(tmp['DATE'], errors='coerce')
                                    tmp.sort_values('DATE', inplace=True)
                                    tmp['HIGH'] = pd.to_numeric(tmp['HIGH'], errors='coerce')
                                    tmp['LOW'] = pd.to_numeric(tmp['LOW'], errors='coerce')
                                    tmp['52W H'] = tmp['HIGH'].rolling(window=252, min_periods=1).max()
                                    tmp['52W L'] = tmp['LOW'].rolling(window=252, min_periods=1).min()
                                    # Ensure we write the most recent values first (descending by DATE)
                                    # Use requested sort order when writing temporaries
                                    if sort_descending:
                                        combined = tmp.sort_values('DATE', ascending=False)
                                    else:
                                        combined = tmp.sort_values('DATE', ascending=True)
                                except Exception as e:
                                    logging.warning(f"Failed to compute 52W values for {symbol}: {e}")
                            # Ensure DATE is formatted and sort final combined output consistently
                            try:
                                combined['DATE'] = pd.to_datetime(combined['DATE'], errors='coerce').dt.strftime('%Y-%m-%d')
                            except Exception:
                                pass
                            if 'DATE' in combined.columns:
                                combined = combined.sort_values('DATE', ascending=not sort_descending)
                                if sort_descending:
                                    combined = combined.sort_values('DATE', ascending=False)
                                else:
                                    combined = combined.sort_values('DATE', ascending=True)
                            combined.to_csv(save_path, index=False)
                            if os.path.exists(save_path) and not existing_df.empty:
                                updated_files += 1
                                sstatus = symbol_status.setdefault(symbol, {'created': False, 'updated': 0, 'rows_processed': 0, 'error': None})
                                sstatus['updated'] += 1
                            else:
                                created_files += 1
                                sstatus = symbol_status.setdefault(symbol, {'created': False, 'updated': 0, 'rows_processed': 0, 'error': None})
                                sstatus['created'] = True
                    except Exception as e:
                        errors.append({'symbol': symbol, 'error': str(e), 'path': save_path})
                        sstatus = symbol_status.setdefault(symbol, {'created': False, 'updated': 0, 'rows_processed': 0, 'error': None})
                        sstatus['error'] = str(e)
                # keep track of per-symbol row counts
                sstatus = symbol_status.setdefault(symbol, {'created': False, 'updated': 0, 'rows_processed': 0, 'error': None})
                sstatus['rows_processed'] += 1
                processed += 1

    # Persist mapping changes if any unknown symbols were added and not dry_run
        if unknown_symbols and not dry_run:
            try:
                self.update_data(self.data)
                # refresh local cache
                self.all_stocks = self.data.get('all_stocks', {})
            except Exception as e:
                errors.append({'error': f'Failed to persist mapping changes: {e}'})
                # record as global error

        logging.info(f"Done. Processed {processed} rows. Updated files: {updated_files}, created files: {created_files}. (unknown added: {len(unknown_symbols)}).")
        if unknown_symbols:
            logging.info("New symbols added to mapping - consider updating 'data.json' to include proper filenames/company names:")
            logging.info(', '.join(sorted(list(unknown_symbols))[:20]))

        # Write a per-run report
        try:
            logs_dir = join(self.bhavcopy_path, 'logs')
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir, exist_ok=True)
            report = {
                'timestamp': datetime.now().isoformat(),
                'processed_rows': int(processed),
                'created_files': int(created_files),
                'updated_files': int(updated_files),
                'unknown_symbols_count': int(len(unknown_symbols)),
                'unknown_symbols': sorted(list(unknown_symbols)),
                'errors': errors,
                'symbol_status': symbol_status,
                'dry_run': bool(dry_run),
                'bhav_files': bhav_files and [os.path.basename(f) for f in bhav_files] or []
            }
            report_file = join(logs_dir, f"bhav_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(report_file, 'w') as fh:
                json.dump(report, fh, indent=2)
            # Also write a CSV with per-symbol status for quick inspection
            try:
                csv_file = join(logs_dir, f"bhav_ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}_symbols.csv")
                symbol_rows = []
                for sym, st in symbol_status.items():
                    symbol_rows.append({
                        'symbol': sym,
                        'created': bool(st.get('created', False)),
                        'updated': int(st.get('updated', 0)),
                        'rows_processed': int(st.get('rows_processed', 0)),
                        'error': st.get('error', None)
                    })
                try:
                    pd.DataFrame(symbol_rows).to_csv(csv_file, index=False)
                except Exception as e:
                    logging.warning(f"Failed to write symbol CSV report: {e}")
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"Failed to write run report file: {e}")

        return True
    
    # The idea is to find stocks which have crossed over in the last 'n' days only
    def find_recent_golden_crossovers(data_handler, days_back=7):
        """Find stocks with SMA20 crossing above SMA50 in the last 'days_back' days."""
        crossover_stocks = []
        
        for stock in data_handler.all_stocks:
            df = data_handler.open_downloaded_stock(stock)
            if df is None or len(df) < 50:
                continue  # Skip if no data or insufficient data
            
            df['SMA20'] = df['CLOSE'].rolling(window=20).mean()
            df['SMA50'] = df['CLOSE'].rolling(window=50).mean()
            
            # Check for crossover in the last 'days_back' days
            recent_data = df.tail(days_back + 1)  # +1 to check previous day as well
            for i in range(1, len(recent_data)):
                if (recent_data['SMA20'].iloc[i-1] < recent_data['SMA50'].iloc[i-1] and
                    recent_data['SMA20'].iloc[i] > recent_data['SMA50'].iloc[i]):
                    crossover_stocks.append(stock)
                    break  # No need to check further for this stock
        
        return crossover_stocks
