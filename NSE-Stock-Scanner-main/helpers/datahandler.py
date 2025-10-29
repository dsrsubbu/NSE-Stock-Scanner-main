from jugaad_data.nse import stock_df
from .nse_data import NSEData
from jugaad_data.nse import bhavcopy_save

from datetime import date, datetime, timedelta

import pandas as pd
import numpy as np

from os import listdir, mkdir, cpu_count
from shutil import rmtree, os
from os.path import join, expanduser

import json
import warnings
import logging

import random

from multiprocessing import Pool

NSE = NSEData()
from os import remove
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s')

workers = int(0.8*cpu_count())


drop = ['SERIES','PREV. CLOSE','VWAP','VOLUME','VALUE','NO OF TRADES', 'LTP']


class DataHandler:
    def __init__(self, data_path = './data', check_fresh = False):
        '''
        '''
        self.present = date.today()
        self.week_num = self.present.strftime("%W")
        
        self.data_path = data_path
        
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
        bhavcopy_path = join(self.data_path, 'bhavcopy')
        if not os.path.exists(bhavcopy_path):
            os.makedirs(bhavcopy_path)
            logging.info(f"Created directory: {bhavcopy_path}")

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
    
    # def download_bhavcopy(self, start_date: date = None, end_date: date = None, days: int = 7):
    #     '''
    #     Downloads historical Bhavcopy files from the NSE archives.

    #     Args:
    #         start_date (date, optional): The most recent date to start downloading from. 
    #                                      Defaults to today.
    #         end_date (date, optional): The oldest date to download to. 
    #                                    If not provided, it's calculated from `days`.
    #         days (int, optional): The number of days to download for, going backwards from 
    #                               start_date. Used if end_date is not specified. Defaults to 7.
    #     '''
    #     bhavcopy_path = join(self.data_path, 'bhavcopy')
    #     if not os.path.exists(bhavcopy_path):
    #         os.makedirs(bhavcopy_path)
    #         logging.info(f"Created directory: {bhavcopy_path}")

    #     if not start_date:
    #         start_date = date.today()
        
    #     if not end_date:
    #         end_date = start_date - timedelta(days=days)

    #     logging.info(f"Starting Bhavcopy download from {end_date.strftime('%Y-%m-%d')} to {start_date.strftime('%Y-%m-%d')}")

    #     current_date = start_date
    #     while current_date >= end_date:
    #         try:
    #             bhavcopy_save(current_date, bhavcopy_path)
    #             logging.info(f"Successfully downloaded Bhavcopy for {current_date.strftime('%Y-%m-%d')}")
    #         except Exception as e:
    #             logging.warning(f"Could not download Bhavcopy for {current_date.strftime('%Y-%m-%d')}. It might be a holiday. Error: {e}")
    #         current_date -= timedelta(days=1)
        
    #     logging.info("Bhavcopy download process finished.")
