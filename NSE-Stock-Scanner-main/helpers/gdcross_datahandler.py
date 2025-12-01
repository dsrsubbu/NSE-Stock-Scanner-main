import pandas as pd
import mplfinance as mpf
import pandas_ta_classic as ta
import json
import os
from .yfinance_handler import fetch_weekly_ohlc, fetch_monthly_ohlc

class DataHandler:
    """
    A class to handle fetching stock data and finding trading signals.
    """
    def __init__(self, stock_list, short_sma=20, long_sma=50, data_path='data', json_path='data.json', weekly_touch_threshold=0.02, monthly_touch_threshold=0.03):
        """
        Initializes the DataHandler with a list of stock symbols and SMA periods.
        """
        if not isinstance(stock_list, list) or not stock_list:
            raise ValueError("stock_list must be a non-empty list of symbols.")
        if not isinstance(short_sma, int) or not isinstance(long_sma, int) or short_sma <= 0 or long_sma <= 0:
            raise ValueError("SMA periods must be positive integers.")
        if short_sma >= long_sma:
            raise ValueError("short_sma must be less than long_sma.")
        self.short_sma = short_sma
        self.long_sma = long_sma
        # thresholds expressed as fraction (e.g. 0.02 == 2%) for determining
        # whether a daily entry price is 'touching' a weekly/monthly SMA
        self.weekly_touch_threshold = float(weekly_touch_threshold)
        self.monthly_touch_threshold = float(monthly_touch_threshold)
        self.stock_list = stock_list
        self.data_path = data_path
        self._load_hni_data()
        self._load_stock_mappings(json_path)

    def _load_stock_mappings(self, json_path):
        """
        Loads the stock symbol to filename mappings from data.json.
        """
        try:
            with open(json_path, 'r') as f:
                self.stock_mappings = json.load(f).get('all_stocks', {})
        except FileNotFoundError:
            print(f"Warning: JSON file not found at {json_path}. Local data loading will fail.")
            self.stock_mappings = {}

    def _load_hni_data(self):
        """
        Loads HNI (Bulk/Block Deal) data from a local CSV file.
        It's assumed this file is populated by a separate process/scraper.
        """
        hni_file_path = os.path.join('data_bulkdeals', 'all_bulk_deals.csv')
        if not os.path.exists(hni_file_path):
            print(f"Warning: {hni_file_path} not found. HNI analysis will be skipped.")
            self.hni_data = None
            return
        
        self.hni_data = pd.read_csv(hni_file_path, parse_dates=['Date'])
        # Convert Date to UTC to match stock data timezone for comparisons
        self.hni_data['Date'] = self.hni_data['Date'].dt.tz_localize('UTC')
        print("Successfully loaded HNI (Bulk/Block Deal) data.")

    def get_stock_data(self, symbol, period="1y"):
        """
        Fetches historical stock data from local CSV files.
        """
        filename = self.stock_mappings.get(symbol)
        if not filename:
            print(f"Warning: Stock '{symbol}' not found in data.json mappings.")
            return None
        
        file_path = os.path.join(self.data_path, filename)
        if not os.path.exists(file_path):
            print(f"Warning: CSV file not found for {symbol} at {file_path}")
            return None
            
        column_names = ['Date', 'Open', 'High', 'Low', 'Close', '52W_H', '52W_L', 'SYMBOL']
        df = pd.read_csv(
            file_path, 
            header=None, 
            names=column_names, 
            skiprows=1,
            parse_dates=['Date'], 
            index_col='Date'
        )
        # The analysis functions expect a 'Volume' column. Since it's not in the CSV,
        # we'll add a placeholder column. The volume-based confidence score will be removed.
        if 'Volume' not in df.columns:
            df['Volume'] = 0
        # Sort the dataframe by date to ensure calculations are correct
        df.sort_index(inplace=True)
        # Make the index timezone-aware to match now_utc
        df.index = df.index.tz_localize('UTC')
        return df

    def _within_pct(self, value: float, target: float, pct: float) -> bool:
        """Return True when value is within +/- pct of target.

        pct is a fraction (e.g., 0.02 is 2%). Handles target==0 safely.
        """
        try:
            value = float(value)
            target = float(target)
        except Exception:
            return False

        if target == 0:
            # fallback to absolute proximity for zero target
            return abs(value) <= pct

        return abs((value - target) / target) <= float(pct)

    def find_recent_golden_crossovers(self, days_back=7):
        """
        Finds stocks that had a Golden Cross (SMA20 crosses above SMA50)
        within the last 'days_back' days.

        Returns a DataFrame with the stock, crossover date, price, and a confidence score.
        """
        recent_crossovers = []

        # Get the current time in a timezone-aware format (UTC) to prevent comparison errors.
        now_utc = pd.Timestamp.now(tz='UTC')
        
        # Define weights for our confidence score
        RECENCY_WEIGHT = 40
        RSI_WEIGHT = 25
        MACD_WEIGHT = 15
        ADX_WEIGHT = 10
        HNI_WEIGHT = 10 # New weight for HNI activity

        for symbol in self.stock_list:
            # Analyze the symbol with its proper exchange suffix for clarity.
            # print(f"Analyzing {symbol}.NS...")
            df = self.get_stock_data(symbol)
            
            if df is None or len(df) < self.long_sma:
                continue # Not enough data to calculate SMAs

            # 1. Calculate Indicators
            short_sma_col = f'SMA{self.short_sma}'
            long_sma_col = f'SMA{self.long_sma}'
            df[short_sma_col] = ta.sma(df['Close'], length=self.short_sma)
            df[long_sma_col] = ta.sma(df['Close'], length=self.long_sma)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            # Calculate MACD and ADX
            macd = ta.macd(df['Close'])
            adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
            df = pd.concat([df, macd, adx], axis=1) # Append indicator columns
            
            # Drop rows with NaN values after calculations
            df.dropna(inplace=True)
            if df.empty:
                continue

            # 2. Identify Crossovers
            # 'position' is 1 when short SMA > long SMA, and 0 otherwise
            df['position'] = (df[short_sma_col] > df[long_sma_col]).astype(int)
            # 'crossover' is 1 on the day the cross happens, -1 on a cross-down, 0 otherwise
            df['crossover'] = df['position'].diff()

            # 3. Filter for recent golden crosses (crossover == 1)
            recent_cross_df = df[(df['crossover'] == 1) & (df.index >= now_utc - pd.Timedelta(days=days_back))]

            if not recent_cross_df.empty:
                # Get the most recent cross for this stock
                cross_event = recent_cross_df.iloc[-1]
                
                # --- Calculate Confidence Score ---
                
                # a. Recency Score (higher for more recent crosses)
                days_since_cross = (now_utc - cross_event.name).days
                recency_score = max(0, (days_back - days_since_cross) / days_back) * RECENCY_WEIGHT

                # c. RSI Score (higher if RSI is not overbought)
                # Score is 100% if RSI is 50 (neutral), and 0% if RSI is 75 (approaching overbought)
                rsi_val = df['RSI'].iloc[-1] # Use the latest RSI
                rsi_score = max(0, (75 - rsi_val) / (75 - 50)) * RSI_WEIGHT if rsi_val > 50 else RSI_WEIGHT
                
                # d. MACD Score (higher if MACD is bullish)
                # Score is 100% if MACD line is above its signal line
                macd_val = cross_event['MACD_12_26_9']
                macds_val = cross_event['MACDs_12_26_9']
                macd_score = MACD_WEIGHT if macd_val > macds_val else 0

                # e. ADX Score (higher if trend is strong)
                # Score is 100% if ADX is >= 20 (indicating a trend)
                adx_val = cross_event['ADX_14']
                adx_score = ADX_WEIGHT if adx_val >= 20 else 0

                # f. HNI Activity Score (higher if recent bulk/block BUY)
                hni_score = 0
                if self.hni_data is not None:
                    # Look for recent BUY deals for this stock up to the crossover date
                    recent_deals = self.hni_data[
                        (self.hni_data['Symbol'] == symbol) &
                        (self.hni_data['Deal Type'].str.upper() == 'BUY') &
                        (self.hni_data['Date'] <= cross_event.name) &
                        (self.hni_data['Date'] >= cross_event.name - pd.Timedelta(days=30))
                    ]
                    if not recent_deals.empty:
                        hni_score = HNI_WEIGHT

                total_confidence = round(recency_score + rsi_score + macd_score + adx_score + hni_score)

                # --- Suggest Entry/Exit Points ---
                entry_price = cross_event['Close']
                # Set stop-loss slightly below the SMA50 on the cross day for a buffer
                stop_loss_price = cross_event[long_sma_col] * 0.98 
                risk = entry_price - stop_loss_price
                # Calculate target with a 1.5 Risk/Reward ratio
                target_price = entry_price + (risk * 1.5)

                # --- Weekly / Monthly alignment checks ---
                weekly_alignment = False
                monthly_alignment = False
                weekly_touch = False
                try:
                    weekly_df = fetch_weekly_ohlc(symbol, period='1y', use_cache=True)
                    weekly_close = self._extract_close_series(weekly_df)
                    if weekly_close is not None and len(weekly_close) >= self.long_sma:
                        w_short = ta.sma(weekly_close, length=self.short_sma)
                        w_long = ta.sma(weekly_close, length=self.long_sma)
                        # Use the most recent weekly values to decide alignment
                        weekly_alignment = bool(w_short.iloc[-1] > w_long.iloc[-1])
                        # Check if entry price is within configured proximity of either weekly SMA
                        weekly_touch = self._within_pct(entry_price, w_short.iloc[-1], self.weekly_touch_threshold) or self._within_pct(entry_price, w_long.iloc[-1], self.weekly_touch_threshold)
                except Exception:
                    weekly_alignment = False

                monthly_touch = False
                try:
                    monthly_df = fetch_monthly_ohlc(symbol, period='5y', use_cache=True)
                    monthly_close = self._extract_close_series(monthly_df)
                    if monthly_close is not None and len(monthly_close) >= self.long_sma:
                        m_short = ta.sma(monthly_close, length=self.short_sma)
                        m_long = ta.sma(monthly_close, length=self.long_sma)
                        monthly_alignment = bool(m_short.iloc[-1] > m_long.iloc[-1])
                        monthly_touch = self._within_pct(entry_price, m_short.iloc[-1], self.monthly_touch_threshold) or self._within_pct(entry_price, m_long.iloc[-1], self.monthly_touch_threshold)
                except Exception:
                    monthly_alignment = False

                recent_crossovers.append({
                    'Stock': symbol,
                    'Crossover Date': cross_event.name.strftime('%Y-%m-%d'),
                    'Entry Price': f"₹{entry_price:.2f}",
                    'Stop-Loss': f"₹{stop_loss_price:.2f}",
                    'Target (1.5R)': f"₹{target_price:.2f}",
                    'Confidence Score (%)': total_confidence,
                    # Two new columns show whether the short/long SMA relationship
                    # on the weekly / monthly timeframe matches the daily bullish cross
                    'Weekly Alignment': 'Yes' if weekly_alignment else 'No',
                    'Monthly Alignment': 'Yes' if monthly_alignment else 'No',
                    'Weekly Touch': 'Yes' if weekly_touch else 'No',
                    'Monthly Touch': 'Yes' if monthly_touch else 'No'
                })

        if not recent_crossovers:
            return "No recent golden crossovers found in the provided stock list."
            
        return pd.DataFrame(recent_crossovers).sort_values(by='Confidence Score (%)', ascending=False).reset_index(drop=True)

    def find_recent_death_crossovers(self, days_back=7):
        """
        Finds stocks that had a Death Cross (short_sma crosses below long_sma)
        within the last 'days_back' days.

        Returns a DataFrame with the stock, crossover date, price, and a confidence score.
        """
        recent_crossovers = []
        now_utc = pd.Timestamp.now(tz='UTC')
        
        # Weights can be the same, but their application will differ
        RECENCY_WEIGHT = 40
        RSI_WEIGHT = 25
        MACD_WEIGHT = 15
        ADX_WEIGHT = 10
        HNI_WEIGHT = 10 # New weight for HNI activity

        for symbol in self.stock_list:
            # print(f"Analyzing {symbol}.NS for Death Cross...")
            df = self.get_stock_data(symbol)
            
            if df is None or len(df) < self.long_sma:
                continue

            # 1. Calculate Indicators
            short_sma_col = f'SMA{self.short_sma}'
            long_sma_col = f'SMA{self.long_sma}'
            df[short_sma_col] = ta.sma(df['Close'], length=self.short_sma)
            df[long_sma_col] = ta.sma(df['Close'], length=self.long_sma)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            macd = ta.macd(df['Close'])
            adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
            df = pd.concat([df, macd, adx], axis=1)
            df.dropna(inplace=True)
            if df.empty:
                continue

            # 2. Identify Crossovers
            df['position'] = (df[short_sma_col] > df[long_sma_col]).astype(int)
            df['crossover'] = df['position'].diff()

            # 3. Filter for recent death crosses (crossover == -1)
            recent_cross_df = df[(df['crossover'] == -1) & (df.index >= now_utc - pd.Timedelta(days=days_back))]

            if not recent_cross_df.empty:
                cross_event = recent_cross_df.iloc[-1]
                
                # --- Calculate Confidence Score for Bearish Signal ---
                
                # a. Recency Score (same as golden cross)
                days_since_cross = (now_utc - cross_event.name).days
                recency_score = max(0, (days_back - days_since_cross) / days_back) * RECENCY_WEIGHT

                # c. RSI Score (higher if RSI is not oversold)
                # Score is 100% if RSI is 50 (neutral), and 0% if RSI is 25 (approaching oversold)
                rsi_val = df['RSI'].iloc[-1]
                rsi_score = max(0, (rsi_val - 25) / (50 - 25)) * RSI_WEIGHT if rsi_val < 50 else RSI_WEIGHT
                
                # d. MACD Score (higher if MACD is bearish)
                # Score is 100% if MACD line is below its signal line
                macd_val = cross_event['MACD_12_26_9']
                macds_val = cross_event['MACDs_12_26_9']
                macd_score = MACD_WEIGHT if macd_val < macds_val else 0

                # e. ADX Score (higher if trend is strong, same as golden cross)
                adx_val = cross_event['ADX_14']
                adx_score = ADX_WEIGHT if adx_val >= 20 else 0

                # f. HNI Activity Score (higher if recent bulk/block SELL)
                hni_score = 0
                if self.hni_data is not None:
                    # Look for recent SELL deals for this stock up to the crossover date
                    recent_deals = self.hni_data[
                        (self.hni_data['Symbol'] == symbol) &
                        (self.hni_data['Deal Type'].str.upper() == 'SELL') &
                        (self.hni_data['Date'] <= cross_event.name) &
                        (self.hni_data['Date'] >= cross_event.name - pd.Timedelta(days=30))
                    ]
                    if not recent_deals.empty:
                        hni_score = HNI_WEIGHT


                total_confidence = round(recency_score + rsi_score + macd_score + adx_score + hni_score)

                # --- Suggest Entry/Exit Points for a Short Position ---
                entry_price = cross_event['Close']
                # Set stop-loss slightly above the long SMA on the cross day
                stop_loss_price = cross_event[long_sma_col] * 1.02 
                risk = stop_loss_price - entry_price
                # Calculate target with a 1.5 Risk/Reward ratio
                target_price = entry_price - (risk * 1.5)

                # --- Weekly / Monthly alignment and touching checks (bearish) ---
                weekly_alignment = False
                monthly_alignment = False
                weekly_touch = False
                monthly_touch = False
                try:
                    weekly_df = fetch_weekly_ohlc(symbol, period='1y', use_cache=True)
                    weekly_close = self._extract_close_series(weekly_df)
                    if weekly_close is not None and len(weekly_close) >= self.long_sma:
                        w_short = ta.sma(weekly_close, length=self.short_sma)
                        w_long = ta.sma(weekly_close, length=self.long_sma)
                        # For a death cross, higher timeframe agreeing means weekly short < weekly long
                        weekly_alignment = bool(w_short.iloc[-1] < w_long.iloc[-1])
                        weekly_touch = self._within_pct(entry_price, w_short.iloc[-1], self.weekly_touch_threshold) or self._within_pct(entry_price, w_long.iloc[-1], self.weekly_touch_threshold)
                except Exception:
                    weekly_alignment = False

                try:
                    monthly_df = fetch_monthly_ohlc(symbol, period='5y', use_cache=True)
                    monthly_close = self._extract_close_series(monthly_df)
                    if monthly_close is not None and len(monthly_close) >= self.long_sma:
                        m_short = ta.sma(monthly_close, length=self.short_sma)
                        m_long = ta.sma(monthly_close, length=self.long_sma)
                        monthly_alignment = bool(m_short.iloc[-1] < m_long.iloc[-1])
                        monthly_touch = self._within_pct(entry_price, m_short.iloc[-1], self.monthly_touch_threshold) or self._within_pct(entry_price, m_long.iloc[-1], self.monthly_touch_threshold)
                except Exception:
                    monthly_alignment = False

                recent_crossovers.append({
                    'Stock': symbol,
                    'Crossover Date': cross_event.name.strftime('%Y-%m-%d'),
                    'Short Entry': f"₹{entry_price:.2f}",
                    'Stop-Loss': f"₹{stop_loss_price:.2f}",
                    'Target (1.5R)': f"₹{target_price:.2f}",
                    'Confidence Score (%)': total_confidence,
                    'Weekly Alignment': 'Yes' if weekly_alignment else 'No',
                    'Monthly Alignment': 'Yes' if monthly_alignment else 'No',
                    'Weekly Touch': 'Yes' if weekly_touch else 'No',
                    'Monthly Touch': 'Yes' if monthly_touch else 'No'
                })

        if not recent_crossovers:
            return "No recent death crosses found in the provided stock list."
            
        return pd.DataFrame(recent_crossovers).sort_values(by='Confidence Score (%)', ascending=False).reset_index(drop=True)

    def plot_stock_chart(self, symbol, days_back=10):
        """
        Plots the stock chart for a given symbol, highlighting the recent golden cross.
        """
        print(f"\nGenerating chart for {symbol}.NS...")
        df = self.get_stock_data(symbol, period="8mo") # Use 8 months of data for better visualization

        if df is None or len(df) < self.long_sma:
            print(f"Could not generate chart for {symbol}. Not enough data.")
            return

        # Calculate indicators
        short_sma_col = f'SMA{self.short_sma}'
        long_sma_col = f'SMA{self.long_sma}'
        df[short_sma_col] = ta.sma(df['Close'], length=self.short_sma)
        df[long_sma_col] = ta.sma(df['Close'], length=self.long_sma)
        df.dropna(inplace=True)

        # Find the specific crossover event to mark on the chart
        df['position'] = (df[short_sma_col] > df[long_sma_col]).astype(int)
        df['crossover'] = df['position'].diff()
        
        now_utc = pd.Timestamp.now(tz='UTC')
        recent_cross_df = df[(df['crossover'] == 1) & (df.index >= now_utc - pd.Timedelta(days=days_back))]

        vline = None
        if not recent_cross_df.empty:
            cross_date = recent_cross_df.index[-1]
            vline = [cross_date.strftime('%Y-%m-%d')]
            print(f"Golden Cross identified on: {cross_date.strftime('%Y-%m-%d')}")

        # Don't plot volume if it's constant or zero (avoids mplfinance y-lim warnings)
        vol_series = df.get('Volume')
        vol_flag = False
        if vol_series is not None:
            try:
                # require >1 unique values and a positive sum for realistic volume
                vol_flag = (vol_series.dropna().nunique() > 1) and (vol_series.dropna().sum() > 0)
            except Exception:
                vol_flag = False

        mpf.plot(df,
                 type='candle',
                 style='yahoo',
                 title=f'{symbol}.NS - Golden Cross Analysis',
                 ylabel='Price (₹)',
                 mav=(20, 50),
                 volume=vol_flag,
                 vlines=dict(vlines=vline, linewidths=1, colors='g', alpha=0.8) if vline else None,
                 figratio=(16,8))

    def plot_stock_chart_death_cross(self, symbol, days_back=10):
        """
        Plots the stock chart for a given symbol, highlighting the recent death cross.
        """
        print(f"\nGenerating chart for {symbol}.NS...")
        df = self.get_stock_data(symbol, period="8mo")

        if df is None or len(df) < self.long_sma:
            print(f"Could not generate chart for {symbol}. Not enough data.")
            return

        # Calculate indicators
        short_sma_col = f'SMA{self.short_sma}'
        long_sma_col = f'SMA{self.long_sma}'
        df[short_sma_col] = ta.sma(df['Close'], length=self.short_sma)
        df[long_sma_col] = ta.sma(df['Close'], length=self.long_sma)
        df.dropna(inplace=True)

        # Find the specific crossover event to mark on the chart
        df['position'] = (df[short_sma_col] > df[long_sma_col]).astype(int)
        df['crossover'] = df['position'].diff()
        
        now_utc = pd.Timestamp.now(tz='UTC')
        recent_cross_df = df[(df['crossover'] == -1) & (df.index >= now_utc - pd.Timedelta(days=days_back))]

        vline = None
        if not recent_cross_df.empty:
            cross_date = recent_cross_df.index[-1]
            vline = [cross_date.strftime('%Y-%m-%d')]
            print(f"Death Cross identified on: {cross_date.strftime('%Y-%m-%d')}")

        # Plotting using mplfinance, with a red line for the death cross
        vol_series = df.get('Volume')
        vol_flag = False
        if vol_series is not None:
            try:
                vol_flag = (vol_series.dropna().nunique() > 1) and (vol_series.dropna().sum() > 0)
            except Exception:
                vol_flag = False

        mpf.plot(df, type='candle', style='yahoo',
                 title=f'{symbol}.NS - Death Cross Analysis',
                 ylabel='Price (₹)', mav=(self.short_sma, self.long_sma), volume=vol_flag,
                 vlines=dict(vlines=vline, linewidths=1, colors='r', alpha=0.8) if vline else None,
                 figratio=(16,8))

    def _extract_close_series(self, df: pd.DataFrame) -> pd.Series | None:
        """Safely extract a single Close series from yfinance or local dataframes.

        yfinance sometimes returns MultiIndex columns (e.g. ('Close', 'TICKER')), so
        we try a few fallbacks and return a cleaned pd.Series or None.
        """
        if df is None or df.empty:
            return None

        # Direct 'Close' column (normal local CSVs)
        if 'Close' in df.columns:
            close_col = df['Close']
            # if selecting 'Close' returns a DataFrame (multi-col), pick the last column
            if isinstance(close_col, pd.DataFrame):
                return close_col.iloc[:, -1].dropna()
            return close_col.dropna()

        # MultiIndex returned by yfinance: try to find any column whose first or last
        # level equals 'Close'
        if isinstance(df.columns, pd.MultiIndex):
            for col in reversed(df.columns):
                if 'close' == str(col[0]).lower() or 'close' == str(col[-1]).lower():
                    return df[col].dropna()

        # Try to find any column with 'close' in its name (case-insensitive)
        for col in df.columns:
            if 'close' in str(col).lower():
                return df[col].dropna()

        return None

# --- Example Usage ---
# Define your list of stocks to screen
my_stocks = ['360ONE', '3PLAND', 'ABINFRA', 'AAKASH', 'AAVAS', 'AFSL', 'ABBOTINDIA', 'ACCURACY', 'ABCAPITAL', 'ABLBL', 'BIRLAMONEY', 'ADOR', 'ADVANIHOTR', 'AEGISLOG', 'AEROFLEX', 'AETHER', 'AGRITECH', 'AHLUCONT', 'AIRAN', 'AKSHOPTFBR', 'ALLTIME', 'ALLDIGI', 'ALPHAGEO', 'AMBER', 'AMRUTANJAN', 'ANDHRSUGAR', 'APCL', 'ANMOL', 'ANTGRAPHIC', 'APOLLO', 'APOLSINHOT', 'ADL', 'ARCHIDPLY', 'ARIHANTCAP', 'ARISINFRA', 'ARKADE', 'ARROWGREEN', 'ASHOKLEY', 'ASIANTILES', 'ASIANHOTNR', 'ASKAUTOLTD', 'ASTRAMICRO', 'AURIONPRO', 'AUSOMENT', 'AUTOIND', 'AVANTEL', 'AVTNPL', 'BAGFILMS', 'BAJAJCON', 'BAJAJELEC', 'BAJAJHIND', 'BAJEL', 'BALAXI', 'BANARISUG', 'BBNPNBETF', 'BBNPPGOLD', 'BCLIND', 'BEDMUTHA', 'BELLACASA', 'BESTAGRO', 'BILVYAPAR', 'BIRLACABLE', 'ABSLLIQUID', 'BBOX', 'BLACKBUCK', 'BLUEJET', 'BLUESTARCO', 'BBTC', 'BOMDYEING', 'BORANA', 'BOROLTD', 'BOROSCI', 'BPL', 'BSE', 'BUTTERFLY', 'CANFINHOME', 'CANTABIL', 'CAPITALSFB', 'CARYSIL', 'CCL', 'CHOLAHLDNG', 'CIEINDIA', 'CINELINE', 'CINEVISTA', 'COMSYN', 'COMPUSOFT', 'CAMS', 'CEWATER', 'CONFIPET', 'COSMOFIRST', 'CPCAP', 'CRISIL', 'CSLFINANCE', 'DBCORP', 'DAVANGERE', 'DBSTOCKBRO', 'DCI', 'DDEVPLSTIK', 'DEEPINDS', 'DELHIVERY', 'DELTACORP', 'DELTAMAGNT', 'DENTA', 'DHAMPURSUG', 'DHRUV', 'DHUNINV', 'DVL', 'DIACABS', 'DIFFNKG', 'DGCONTENT', 'DIGIDRIVE', 'DBL', 'DJML', 'DOLATALGO', 'DPSCLTD', 'DRCSYSTEMS', 'DREAMFOLKS', 'KEEPLEARN', 'HEALTHADD', 'TOP10ADD', 'DSSL', 'E2E', 'EASEMYTRIP', 'EBANKNIFTY', 'ECAPINSURE', 'ELDEHSG', 'EMIL', 'ELIN', 'EMAMIPAP', 'EMMBI', 'EMSLIMITED', 'EMUDHRA', 'ENTERO', 'EPACK', 'ERIS', 'EVEREADY', 'EKC', 'EXXARO', 'FMGOETZE', 'FILATEX', 'FINOPB', 'FIVESTAR', 'FOCUS', 'FUSION', 'GRINFRA', 'GANESHBE', 'GANGESSECU', 'GRWRHITECH', 'GVT&D', 'GEEKAYWIRE', 'GENUSPAPER', 'GENUSPOWER', 'GHCLTEXTIL', 'GKWLIMITED', 'GSLSU', 'GLOBE', 'GMMPFAUDLR', 'GNA', 'GODFRYPHLP', 'GOKEX', 'GOKULAGRO', 'GOPAL', 'GOYALALUM', 'GULFPETRO', 'GRASIM', 'GRMOVER', 'GROWWGOLD', 'GROWWLOVOL', 'HGINFRA', 'HARDWYN', 'HARSHA', 'HATSUN', 'HDBFS', 'HDFCLIQUID', 'HDFCLOWVOL', 'HDFCMOMENT', 'HDFCNEXT50', 'HDFCNIF100', 'HDFCPSUBK', 'HCG', 'HESTERBIO', 'HEXT', 'HITECH', 'HIRECT', 'HPIL', 'HISARMETAL', 'HONDAPOWER', 'HONAUT', 'HPAL', 'HUHTAMAKI', 'ICICIBANK', 'ICICIGI', 'EVIETF', 'LIQUIDIETF', 'BANKIETF', 'TOP15IETF', 'VAL30IETF', 'ICRA', 'IFBIND', 'IGARASHI', 'IVC', 'BAJAJINDEF', 'INDIAMART', 'IMFA', 'INDORAMA', 'INDOUS', 'IGCL', 'INDOSTAR', 'INTLCONV', 'ISFT', 'IONEXCHANG', 'IPCALAB', 'IRB', 'IRIS', 'IRISDOREME', 'JAGRAN', 'JISLDVREQS', 'JAMNAAUTO', 'JSFB', 'JAYAGROGN', 'JAYNECOIND', 'JETFREIGHT', 'JPOLYINVST', 'JINDALSAW', 'JCHAC', 'JTLIND', 'JLHL', 'JYOTISTRUC', 'KMSUGAR', 'KABRAEXTRU', 'KALPATARU', 'KALYANIFRG', 'KANPRPLA', 'KCPSUGIND', 'KDDL', 'KEYFINSERV', 'KFINTECH', 'KHADIM', 'KIRLOSBROS', 'KECL', 'KNRCON', 'KOPRAN', 'QUALITY30', 'KRBL', 'KRIDHANINF', 'KRISHANA', 'KRITIKA', 'KROSS', 'KRYSTAL', 'LANCORHOL', 'LPDC', 'LATENTVIEW', 'LAXMIDENTL', 'LGHL', 'LIBERTSHOE', 'LINCOLN', 'LLOYDSENT', 'LOVABLE', 'LUMAXTECH', 'MBEL', 'MAANALU', 'MCLOUD', 'MAHAPEXLTD', 'MAHSEAMLES', 'M&M', 'MHRIL', 'MAMATA', 'MANAKCOAT', 'MANAKSIA', 'MANCREDIT', 'MANGALAM', 'MGEL', 'MANORG', 'MANORAMA', 'MARINE', 'MARUTI', 'MASFIN', 'MATRIMONY', 'MAWANASUG', 'MAZDA', 'MBLINFRA', 'MEDIASSIST', 'MENONBE', 'MICEL', 'CONSUMER', 'LIQUID', 'MIDSMALL', 'MULTICAP', 'MIRZAINT', 'MITTAL', 'MMP', 'MODTHREAD', 'MOKSH', 'MOLDTKPAC', 'MONARCH', 'MOSCHIP', 'MOALPHA50', 'MODEFENCE', 'MOINFRA', 'MOMENTUM50', 'MOMGF', 'MOMIDMTM', 'MOTOUR', 'MOTOGENFIN', 'BECTORFOOD', 'MSPL', 'MUKKA', 'MUKTAARTS', 'MURUDCERA', 'NDGL', 'NAHARINDUS', 'NAHARPOLY', 'NAHARSPING', 'NGIL', 'NSIL', 'JAIPURKURT', 'NPST', 'NEWGEN', 'NIBE', 'NIITLTD', 'LIQUIDBEES', 'SNXT30BEES', 'NITCO', 'NITINSPIN', 'NITIRAJ', 'NKIND', 'NECCLTD', 'NUCLEUS', 'NRL', 'NUVAMA', 'OMAXE', 'ONMOBILE', 'ORBTEXP', 'ORIENTCER', 'ORIENTPPR', 'OBCL', 'PNGJL', 'PAKKA', 'PALASHSECU', 'PARASPETRO', 'PARKHOTELS', 'PASHUPATI', 'PASUPTAC', 'PDSL', 'PGIL', 'PIONEEREMB', 'PLASTIBLEN', 'PLATIND', 'PLAZACABLE', 'POLYPLEX', 'PONNIERODE', 'PVSL', 'PPAP', 'PRAKASH', 'PREMIERENE', 'PREMIERPOL', 'PRIMESECU', 'PRIMO', 'PGHL', 'PRUDENT', 'PRUDMOULI', 'PTL', 'QUADFUTURE', 'QPOWER', 'RADHIKAJWE', 'RADIANTCMS', 'RAIN', 'ROML', 'RAJESHEXPO', 'RAJOOENG', 'RAMASTEEL', 'RKFORGE', 'RANASUG', 'RPTECH', 'RATNAVEER', 'RAYMOND', 'REDTAPE', 'REGENCERAM', 'RELIGARE', 'RGL', 'REPCOHOME', 'RBA', 'RICOAUTO', 'RKEC', 'ROSSTECH', 'ROTO', 'RPGLIFE', 'RUCHINFRA', 'RUPA', 'S&SPOWER', 'SAILIFE', 'SAKSOFT', 'SAKHTISUG', 'SALONA', 'SAMBHAAV', 'SANATHAN', 'SANGHVIMOV', 'SANOFICONR', 'SSDL', 'SARDAEN', 'SARVESHWAR', 'SATIN', 'SAURASHCEM', 'SBILIFE', 'LIQUIDSBI', 'SBISILVER', 'SEMAC', 'SEPC', 'SERVOTECH', 'SGFIN', 'SHAILY', 'SHAKTIPUMP', 'SHANKARA', 'SHANTIGOLD', 'SHANTI', 'SHILPAMED', 'SHIVATEX', 'SHIVALIK', 'SHIVAMAUTO', 'RENUKA', 'BALAJEE', 'SHREEJISPG', 'SHREYANIND', 'SIGACHI', 'SIGIND', 'SINDHUTRAD', 'SINTERCOM', 'SIRCA', 'SKIPPER', 'SMLISUZU', 'SONAMLTD', 'SONATSOFTW', 'SOUTHWEST', 'HAVISHA', 'LOTUSDEV', 'SRM', 'SGLTL', 'STARHEALTH', 'SSWL', 'STEELCAS', 'SUNDRMBRAK', 'SUNCLAY', 'SUNDARAM', 'SUNDRMFAST', 'SUNDROP', 'SUNTECK', 'SUPERSPIN', 'SUPREME', 'SPLPETRO', 'SURYODAY', 'SUTLEJTEX', 'SUYOG', 'SWELECTES', 'SYMPHONY', 'SYNGENE', 'TTML', 'TDPOWERSYS', 'TPHQ', 'NIACL', 'UGARSUGAR', 'WIPL', 'THEJO', 'THEMISMED', 'THOMASCOOK', 'TIL', 'TIMETECHNO', 'TIPSFILMS', 'TIPSMUSIC', 'TOTAL', 'TOUCHWOOD', 'TPLPLASTEH', 'TCI', 'TRANSWORLD', 'TRF', 'TRITURBINE', 'TTKPRESTIG', 'TVVISION', 'UGROCAP', 'UNIPARTS', 'UNIVCABLES', 'UNIVPHOTO', 'UMESLTD', 'USHAMART', 'NIF10GETF', 'NIF5GETF', 'UTINIFTETF', 'VGUARD', 'VADILALIND', 'VAIBHAVGBL', 'VALIANTLAB', 'DBREALTY', 'VSSL', 'VTL', 'VARROC', 'VASCONEQ', 'VENKEYS', 'VENTIVE', 'VENUSPIPES', 'VIDHIING', 'VIMTALABS', 'VINATIORGA', 'VINDHYATEL', 'VINNY', 'VIPCLOTHNG', 'VISAKAIND', 'VISHWARAJ', 'WSI', 'WAAREEENER', 'WAAREERTL', 'WANBURY', 'WEIZMANIND', 'WELENT', 'WELSPUNLIV', 'WSTCSTPAPR', 'WHIRLPOOL', 'WONDERLA', 'XTGLOBAL', 'YATHARTH', 'ZAGGLE', 'ZEEMEDIA', 'ZENITHEXPO', 'ZFCVINDIA', 'ZODIACLOTH', 'TSFINV', 'PARSVNATH']

# Create the handler and run the analysis
# Using 50/200 day SMAs, a more traditional setup for crosses
DH = DataHandler(stock_list=my_stocks, short_sma=20, long_sma=50)

# --- Find Golden Crosses (Bullish) ---
print("\n--- Searching for Golden Crosses ---")
golden_cross_data = DH.find_recent_golden_crossovers(days_back=30)
print(golden_cross_data)

# --- Find Death Crosses (Bearish) ---
print("\n--- Searching for Death Crosses ---")
death_cross_data = DH.find_recent_death_crossovers(days_back=30)
# print(death_cross_data)

# --- Plotting Example for a Death Cross ---
if isinstance(death_cross_data, pd.DataFrame) and not death_cross_data.empty:
    top_stock_symbol = death_cross_data.iloc[0]['Stock']
    DH.plot_stock_chart_death_cross(top_stock_symbol, days_back=30)
