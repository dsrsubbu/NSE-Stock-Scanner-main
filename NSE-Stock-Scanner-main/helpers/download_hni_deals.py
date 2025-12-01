import requests
import pandas as pd
from datetime import date, timedelta
from io import StringIO
import os
import io
import zipfile
import gzip
import time

def fetch_nse_deals(start_date: date, end_date: date) -> pd.DataFrame:
    """
    Fetches bulk and block deal data for a specific date range from the NSE India website.

    Args:
        start_date: The start date for the report.
        end_date: The end date for the report.

    Returns:
        A pandas DataFrame containing the deal data, or an empty DataFrame if no data is found or an error occurs.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers) # Visit main page to get cookies

    from_date_str = start_date.strftime('%d-%m-%Y')
    to_date_str = end_date.strftime('%d-%m-%Y')

    all_deals = []
    deal_types = ['bulk_deals', 'block_deals']

    for deal_type in deal_types:
        try:
            url = f"https://www.nseindia.com/api/historicalOR/bulk-block-short-deals?optionType={deal_type}&from={from_date_str}&to={to_date_str}&csv=true"
            print(f"Fetching {deal_type} from {from_date_str} to {to_date_str}...")
            response = session.get(url, headers=headers, timeout=30) # Increased timeout to 30 seconds
            response.raise_for_status()

            # The NSE API historically returns a zip containing a CSV, but depending on
            # the request/headers it can return plain CSV, gzip, or an HTML error page.
            content_bytes = response.content
            content = None

            # Detect zip by magic bytes PK\x03\x04
            if content_bytes.startswith(b'PK\x03\x04'):
                try:
                    with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
                        csv_filename = zf.namelist()[0]
                        with zf.open(csv_filename) as f:
                            content = f.read().decode('utf-8')
                except zipfile.BadZipFile:
                    # Fall through to try other handlers below
                    print(f"Warning: response looked like a zip but couldn't be read as one for {deal_type}.")

            # Detect gzip by magic bytes 0x1f 0x8b
            if content is None and content_bytes.startswith(b'\x1f\x8b'):
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(content_bytes)) as gf:
                        content = gf.read().decode('utf-8')
                except Exception:
                    print(f"Warning: failed to decode gzip response for {deal_type}.")

            # If still no content, try to decode as text (CSV or HTML)
            if content is None:
                try:
                    content = content_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # fallback with replacement to avoid crashes
                    content = content_bytes.decode('utf-8', errors='replace')

            # If the server returned HTML (e.g., 403 page or captcha), show a small snippet
            lowered = content.lower() if isinstance(content, str) else ''
            if '<html' in lowered or 'access denied' in lowered or 'unauthorized' in lowered:
                print(f"Unexpected HTML response for {deal_type} (possible block). Response headers: {response.headers}")
                print("Response snippet:\n" + content[:1000])
                continue

            
            if "no records found" in content.lower():
                print(f"No {deal_type} found for the given date range.")
                continue

            # Find the actual CSV header line (some responses include a descriptive
            # first line like "Date: ..." before the CSV header). Locate the first
            # line that contains both 'Date' and 'Symbol' and treat it as header.
            lines = content.splitlines()
            header_idx = 0
            for i, line in enumerate(lines[:10]):
                if 'date' in line.lower() and 'symbol' in line.lower():
                    header_idx = i
                    break

            csv_data = StringIO('\n'.join(lines[header_idx:]))
            df = pd.read_csv(
                csv_data, 
                sep=',', 
                thousands=',', # Handle numbers like "83,001"
                quotechar='"',
                skipinitialspace=True # Handle whitespace after delimiter
            )
            
            # Standardize columns
            df.columns = [col.strip() for col in df.columns]
            df.rename(columns={
                'Symbol': 'Symbol',
                'Client Name': 'Client Name',
                'Buy / Sell': 'Deal Type', # Header from sample
                'Quantity Traded': 'Quantity',
                'Trade Price / Wght. Avg. Price': 'Price'
            }, inplace=True)
            try:
                df['Date'] = pd.to_datetime(df['Date'], format='%d-%b-%Y')
            except Exception as e:
                print(f"Failed to parse 'Date' column for {deal_type}. Columns found: {list(df.columns)}")
                print("First few lines of content:\n" + "\n".join(lines[:10]))
                raise
            
            all_deals.append(df[['Date', 'Symbol', 'Client Name', 'Deal Type', 'Quantity', 'Price']])

        except requests.exceptions.RequestException as e:
            print(f"Error fetching {deal_type}: {e}")
        except Exception as e:
            print(f"An error occurred while processing {deal_type}: {e}")
        
        time.sleep(2) # Be a good citizen and add a delay between requests

    if not all_deals:
        return pd.DataFrame()

    # Filter out empty DataFrames or DataFrames with only all-NA rows/columns
    valid_deals = []
    for df in all_deals:
        if not isinstance(df, pd.DataFrame):
            continue
        # Skip completely empty DataFrames
        if df.empty:
            continue
        # If dropping rows that are all-NA results in empty, skip it
        if df.dropna(how='all').empty:
            continue
        valid_deals.append(df)

    if not valid_deals:
        return pd.DataFrame()

    return pd.concat(valid_deals, ignore_index=True)


if __name__ == "__main__":
    # --- Configuration ---
    OUTPUT_DIR = 'data_bulkdeals'
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'all_bulk_deals.csv')

    # Ensure the output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    existing_deals_df = pd.DataFrame()
    # --- Append Logic ---
    # Check if the file already exists to determine the start date for fetching.
    if os.path.exists(OUTPUT_FILE):
        print(f"Found existing file: {OUTPUT_FILE}. Reading for append operation.")
        existing_deals_df = pd.read_csv(OUTPUT_FILE, parse_dates=['Date'])
        # Start fetching from the day after the last recorded date.
        start_date = existing_deals_df['Date'].max().date() + timedelta(days=1)
    else:
        print("No existing file found. Fetching data for the last 365 days.")
        # If no file, fetch the last year of data as a starting point.
        start_date = date.today() - timedelta(days=365)

    end_date = date.today()

    # --- Main Execution ---
    if start_date > end_date:
        print("Deal data is already up-to-date. No new data to fetch.")
    else:
        print("Starting HNI Deal Scraper...")
        new_deals_df = fetch_nse_deals(start_date, end_date)

        if not new_deals_df.empty:
            # Combine old and new data
            final_df = pd.concat([existing_deals_df, new_deals_df], ignore_index=True)
            
            # Clean up data: remove duplicates and sort
            final_df.drop_duplicates(subset=['Date', 'Symbol', 'Client Name', 'Deal Type', 'Quantity'], inplace=True)
            final_df.sort_values(by='Date', ascending=False, inplace=True)
            
            # Save to CSV, overwriting the old file with the combined and cleaned data
            final_df.to_csv(OUTPUT_FILE, index=False)
            print(f"\nSuccessfully updated {OUTPUT_FILE}. Total deals: {len(final_df)}.")
        else:
            print("\nNo new deals found in the specified date range.")


    # You will also need to update the DataHandler to read from the new file name.
    # In 'helpers/yfinance_datahandler.py', change:
    # hni_file_path = os.path.join(self.data_path, 'hni_deals.csv')
    # TO
    # hni_file_path = os.path.join('data_bulkdeals', 'all_bulk_deals.csv')
    # And ensure the main script initializes DataHandler with the correct path if needed.
