import pandas as pd
import requests
from datetime import date, datetime,timedelta
from bs4 import BeautifulSoup
import json
import zipfile, io
import gzip
import zlib
try:
    import brotli
    _HAS_BROTLI = True
except Exception:
    _HAS_BROTLI = False

current_date = date.today()

class NSEData:
    '''
    Class to open NSE data
    '''
    def __init__(self,):
        '''
        '''
        self.baseurl = "https://www.nseindia.com/"

        self.headers = {"user-agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36", "accept-encoding": "gzip, deflate, br",
              "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,la;q=0.7",
              "sec-ch-ua-platform": "Linux", "sec-ch-ua": '"Chromium";v="94", "Google Chrome";v="94", ";Not A Brand";v="99"'}


        self.to = current_date.strftime("%d-%m-%Y") # For getting historical data
        self.from_ = current_date.replace(year = current_date.year-2).strftime("%d-%m-%Y") # for getting historical data

        self._force_reset_session()

    
    def _force_reset_session(self):
        self.session = requests.Session()
        # Disable automatic decompression so we can handle it manually
        self.session.headers.update({'Accept-Encoding': 'gzip, deflate, br'})
        # Disable auto-decompression
        self.session.stream = False
        request = self.session.get(self.baseurl, headers=self.headers)
        self.cookies = dict(request.cookies)

        
    def get_live_nse_data(self, url:str, retries:int = 3, backoff:float = 2.0):
        '''
        Get Live market data available on NSE website. Retries on connection errors with exponential backoff.
        args:
           url: corresponding url
           retries: number of retry attempts
           backoff: backoff multiplier for exponential delay
        '''
        import time
        for attempt in range(retries):
            try:
                response = self.session.get(url, headers=self.headers, cookies=self.cookies, timeout=10)
                response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
                return response
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < retries - 1:
                    self._force_reset_session()
                    wait_time = backoff ** attempt
                    time.sleep(wait_time)
                else:
                    raise

        return response


    def _parse_json_response(self, resp):
        """
        Robustly parse a requests.Response as JSON, handling compressed encodings.
        Respects the Content-Encoding header and tries: gzip → zlib → brotli → raw text decode
        """
        content = resp.content
        encoding = resp.headers.get('content-encoding', '').lower()
        
        # Try based on Content-Encoding header first
        if 'gzip' in encoding:
            try:
                decompressed = gzip.decompress(content).decode('utf-8', errors='ignore')
                return json.loads(decompressed)
            except Exception:
                pass
        
        if 'deflate' in encoding:
            try:
                decompressed = zlib.decompress(content).decode('utf-8', errors='ignore')
                return json.loads(decompressed)
            except Exception:
                pass
        
        if 'br' in encoding or 'brotli' in encoding:
            if _HAS_BROTLI:
                try:
                    decompressed = brotli.decompress(content).decode('utf-8', errors='ignore')
                    return json.loads(decompressed)
                except Exception as e:
                    pass
            else:
                import warnings
                warnings.warn("Response is brotli-compressed but 'brotli' module not installed. Install it with: pip install brotli")
        
        # Try as-is first (normal case or auto-decompressed by requests)
        try:
            return resp.json()
        except Exception:
            pass
        
        # Blind attempt: try gzip (magic bytes: 0x1f 0x8b)
        if len(content) >= 2 and content[:2] == b'\x1f\x8b':
            try:
                decompressed = gzip.decompress(content).decode('utf-8', errors='ignore')
                return json.loads(decompressed)
            except Exception:
                pass
        
        # Blind attempt: try zlib
        try:
            decompressed = zlib.decompress(content)
            return json.loads(decompressed.decode('utf-8', errors='ignore'))
        except Exception:
            pass
        
        # Blind attempt: try brotli (last resort)
        if _HAS_BROTLI:
            try:
                decompressed = brotli.decompress(content)
                return json.loads(decompressed.decode('utf-8', errors='ignore'))
            except Exception:
                pass
        
        # Fallback: try to decode raw bytes as UTF-8 and parse JSON
        try:
            text = content.decode('utf-8', errors='ignore')
            if text.strip():
                return json.loads(text)
        except Exception:
            pass
        
        # Last resort: try latin-1 decoding
        try:
            text = content.decode('latin-1', errors='ignore')
            if text.strip():
                return json.loads(text)
        except Exception:
            pass
        
        # If all else fails, return empty dict with warning
        import warnings
        warnings.warn(f"Could not parse response (Content-Encoding: {encoding}). "
                      f"First 100 bytes: {content[:100]!r}")
        return {}
    

    def current_indices_status(self,show_n:int=5):
        '''
        Get current status of all the available indices. It could be pre, dyring or post market. Will tell how much each index or sector moved as other details
        args:
            show_n: Show top N sorted by ABSOLUTE % change Values such that -3.2 will be shown first than 2.3
        '''
        try:
            response = self.get_live_nse_data("https://www.nseindia.com/api/allIndices")
            data = self._parse_json_response(response)
            df = pd.DataFrame(data['data'])
            df['absolute_change'] = df['percentChange'].apply(lambda x: abs(x))
            df.sort_values('absolute_change',ascending=False, inplace=True)
            return df.iloc[:show_n,[1,5,0,4]]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error decoding JSON or key error in current_indices_status: {e}")
            return pd.DataFrame()
    
    
    def open_nse_index(self,index_name:str,show_n:int=10, drop_index:bool = True):
        '''
        Open the current index. DataFrame with all the members of the index and theit respective Open, High, Low, Percentange chnge etc etc
        args:
            index_name: Name of the Index such as NIFTY 50, NIFTY Bank, NIFTY-IT etc
            show_n: Show top N sorted by ABSOLUTE % change Values such that -3.2 will be shown first than 2.3
            driop_index: Whether to drop the Index Value row itsels
        '''
        index_name = index_name.replace(' ','%20')
        index_name = index_name.replace(':','%3A')
        index_name = index_name.replace('/','%2F')
        index_name = index_name.replace('&','%26')

        url = f"https://www.nseindia.com/api/equity-stockIndices?index={index_name}"

        try:
            resp = self.get_live_nse_data(url)
            data = self._parse_json_response(resp)
            df = pd.DataFrame(data['data'])
            df['absolute_change'] = df['pChange'].apply(lambda x: abs(x))
            # df['Index'] = df['symbol'].apply(lambda x: In.get_index(x))
            df.sort_values('absolute_change',ascending=False, inplace=True)

            if drop_index: df.drop(0,inplace = True) # Drop the index name
            # Use .loc with column names to preserve them in the returned DataFrame
            columns_to_return = ['symbol', 'pChange', 'dayHigh', 'dayLow', 'lastPrice', 'prevClose', 'absolute_change']
            df_subset = df[columns_to_return]
            return df_subset.head(show_n)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error decoding JSON or key error in open_nse_index for {index_name}: {e}")
            return pd.DataFrame()
        

    def get_VIX(self, whole_data:bool = False):
        '''
        Get the Volatility Index Value. 
        Read more at: 
        https://tradebrains.in/india-vix/
        https://www.motilaloswal.com/blog-details/6-things-that-the-Volatility-Index-(VIX)-indicates-to-you../1929
        args:
            whole_data: Get the Whole Current +  historical data of VIX
        '''
        try:
            resp = self.get_live_nse_data('https://www1.nseindia.com/live_market/dynaContent/live_watch/VixDetails.json')
            result = self._parse_json_response(resp)
            if whole_data:
                return result
            print(f"Current VIX: {result['currentVixSnapShot'][0]['CURRENT_PRICE']}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error decoding JSON or key error in get_VIX: {e}")
            return None


    def fifty_days_data(self, symbol:str):
        '''
        Get Historical Data for each equity for the past 50 trading days
        args:
            symbol: Listed name of the stock on NSE
        '''
        url = f"https://www.nseindia.com/api/historical/cm/equity?symbol={symbol}&series=[%22EQ%22]&from={self.from_}&to={self.to}"
        try:
            result = self.get_live_nse_data(url = url)
            data = self._parse_json_response(result)
            df = pd.DataFrame(data['data'])
            df.columns = df.columns.map({'CH_SYMBOL':'SYMBOL',"CH_TRADE_HIGH_PRICE":"HIGH","CH_TRADE_LOW_PRICE":"LOW","CH_OPENING_PRICE":"OPEN","CH_CLOSING_PRICE":"CLOSE",
                    "CH_TIMESTAMP":"DATE","CH_52WEEK_LOW_PRICE":"52W L","CH_52WEEK_HIGH_PRICE":"52W H"})

            df = df.loc[:,["DATE","OPEN","HIGH","LOW","CLOSE","52W H","52W L","SYMBOL"]] # to match previous API's Columns and structure
            return df
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error decoding JSON or key error in fifty_days_data for {symbol}: {e}")
            return pd.DataFrame()


    def stocks_at_52W(self, direction:str = 'high' ):
        '''
        Get stocks trading currently at their 52W High / Low
        args:
            direction: direction of 52 Week. 'high', 'low'
        '''
        try:
            x = self.get_live_nse_data(f'https://www.nseindia.com/api/live-analysis-52Week?index={direction}')
            data = self._parse_json_response(x)
            df_greater = pd.DataFrame(data.get('dataLtpGreater20', []))
            df_less = pd.DataFrame(data.get('dataLtpLess20', []))
            if df_greater.empty and df_less.empty:
                return pd.DataFrame()
            return pd.concat([df_greater, df_less], ignore_index=True)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error decoding JSON or key error in stocks_at_52W for {direction}: {e}")
            return pd.DataFrame()


    
class MarketSentiment:
    '''
    Get the market sentiment based on TICK, TRIN etc
    '''
    def check_fresh_data(self):
        '''
        Get fresh updated data scraped from the website https://www.traderscockpit.com/?pageView=live-nse-advance-decline-ratio-chart
        '''
        page = requests.get('https://www.traderscockpit.com/?pageView=live-nse-advance-decline-ratio-chart')
        soup = BeautifulSoup(page.content, "lxml")
        latest_updated_on = soup.find("span", {"class": "hm-time"})
        divs = soup.find_all("div", {"class": "col-sm-6"})
        return divs, latest_updated_on
    
    
    def get_TRIN(self, divs):
        '''
        Get the TRIN or so called Arm's Index of the market at any given point of time. Gives the market sentiment along with TICK. TRIN < 1 is Bullishh and  TRIN > 1 is bearish.
        Values below 0.5 or greater than 3 shows Overbought and Oversold zone respectively. Check: https://www.investopedia.com/terms/a/arms.asp
        args:
            divs: Div elements scraped from website
        returns:
             dictonary of volume in Millions of shares for inclining or declining stocks along with the TRIN value
        '''
        self.volume_up = float(divs[4].text[1:-1])
        self.volume_down = float(divs[5].text[1:-1])
        
        self.trin = float(divs[3].find('h4').text.split(' ')[-1].split(':')[-1][:-1])
        return {'Volume Up':self.volume_up, 'Volume Down': self.volume_down, 'TRIN': self.trin}
    
    
    def get_TICK(self, divs):
        '''
        Get the TICK data for live market. TICK is the difference between the gaining stocks and losing stocks at any point in time. Show nmarket sentiment and health along with TRIN.           Buy/ Long Position if TRIN is > 0; sell/short otherwise
        args:
            divs: BeautifulSoup object of all the div elements.
        returns: Dictonary showing stocks which are up/ down corresponding to LAST tick traded value along with the differene betwwn no of stocks and no of stocks down
        '''
        self.stock_up = int(divs[1].text.split(' ')[-1][:-1])
        self.stock_down = int(divs[2].text.split(' ')[-1][:-1])

        self.tick = self.stock_up - self.stock_down
        return {'Up':self.stock_up, "Down":self.stock_down, 'TICK':self.tick}
    
    
    def get_high_low(self, divs):
        '''
        Get no of stocks trading at 52 Week high or 52 week low at any given point of time
        args:
            divs: BeautifulSoup object of all the div elements
        returns: Dictonary of no of stocks trading at high and low
        '''  
        high = int(divs[7].find('p').text.split(' ')[-1])
        low = int(divs[8].find('p').text.split(' ')[-1])

        return {'52W High':high, "52W Low":low}

    
    def get_live_sentiment(self, print_analysis:bool = True):
        '''
        Get the live sentiment of market based on TICK and TRIN
        args:
            print_analysis: Whether to print only the analysis
        '''
        result = {}
        divs, latest_updated_on = self.check_fresh_data()
        
        result['Latest Updated on'] =  latest_updated_on.text[7:]
        result.update(self.get_TICK(divs))
        result.update(self.get_TRIN(divs))
        result.update(self.get_high_low(divs))

        if print_analysis:
            tick = result['TICK']
            trin = result['TRIN']
            tick_sentiment = 'Bullish' if tick > 0 else "Bearish"
            trin_sentiment = 'Bullish' if trin < 1 else "Bearish"
            if trin > 3:
                print(f'Currently Bearish but may reverse soon due to TRIN value {trin} > 3')

            if trin < 0.5:
                print(f'Currently Bullish but may reverse soon due to TRIN value {trin} < 0.5')

            if tick < 0 and trin > 1:
                print(f"Pure Bearish due to negative tick {tick} and TRIN {trin} > 1")

            if tick > 0 and trin < 1:
                print(f"Pure Bullish due to positive tick {tick} and TRIN {trin} < 1")

            if (tick > 0 and trin > 1) or (tick < 0 and trin < 1):
                print(f"Watch out as TICK {tick} {tick_sentiment} and TRIN {trin} {trin_sentiment} have opposite sentiments")

        return result
    

def get_mmi(raw = False):
    '''
    All credits to https://www.tickertape.in/market-mood-index. Please refer to the link
    args:
        raw: Whether to return the raw json of data for MMI
    '''
    url = "https://www.tickertape.in/market-mood-index"
    page = requests.get(url)
    soup = BeautifulSoup(page.content, "lxml")


    script = soup.find_all('script' ,{"id":"__NEXT_DATA__"})[0]
    values = json.loads(script.string)['props']['pageProps']['nowData']
    current = values['currentValue']
    last_day = values['lastDay']['indicator']
    last_week = values['lastWeek']['indicator']
    last_month = values['lastMonth']['indicator']
    
    if raw:
        return values
    
    if current < 30:
        print('Boom!!! You might want to Buy for Investment purpose. Market is in Extreme Fear')
        
    elif 30 < current < 50:
        print('Market is in Fear Zone. You might want it to go to Extreme Fear to start buying')
        
    elif 50 < current < 80:
        print('Market is in Greed zone! You might want to book profits. Keep yourself from taking new positions')
    
    elif current > 80:
        print("WARNING!!! You might want to book profits. Do not take fresh positions for Investment purpose now. Market is Extremely Greedy")
        

def get_Bhavcopy(start = None, no_days = 5):
    res = []
    if not start:
        start = current_date
        end = start - timedelta(days = no_days)
        
    for i in range(no_days):
        day = start - timedelta(days = i)
        try:
            r = requests.get(f'https://www1.nseindia.com/content/historical/EQUITIES/2022/JAN/cm{day}bhav.csv.zip')
            z = zipfile.ZipFile(io.BytesIO(r.content))
            z = z.open(z.namelist()[0])
            res.append(pd.read_csv(z))
        except:
            pass
    return res
