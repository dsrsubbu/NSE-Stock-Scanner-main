import pandas as pd
import requests
import io

# --- Configuration: Base URL for NSE Index Constituent CSV files ---
# NOTE: The links provided by NSE change occasionally. 
# These are the current, standard index constituent download links from the Nifty Indices website.
BASE_URL = "https://www1.nseindia.com/content/indices/"
INDEX_MAP = {
    "Nifty 50": "ind_nifty50list.csv",
    "Nifty 100": "ind_nifty100list.csv",
    "Nifty 200": "ind_nifty200list.csv",
    "Nifty 500": "ind_nifty500list.csv",
}

# Dictionary to store the final list of symbols
index_symbols = {}
all_symbols = set() # To store a unique list of all symbols across all indices

def get_index_constituents(index_name, file_name):
    """Downloads the CSV file from NSE and extracts the 'Symbol' column."""
    url = f"{BASE_URL}{file_name}"
    print(f"-> Attempting to download: {index_name} from {url}")
    
    try:
        # Use a session to mimic a browser request for better reliability
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        
        response = session.get(url, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes

        # Read the content into a Pandas DataFrame
        content = response.content.decode('utf-8')
        df = pd.read_csv(io.StringIO(content))
        
        # The column containing the symbol is typically named 'Symbol' or similar
        # Fallback to the first column if 'Symbol' is not found
        if 'Symbol' in df.columns:
            symbols = df['Symbol'].tolist()
        else:
            # Fallback (e.g., for Nifty 50, the column is 'Symbol' or 'SNo' followed by Symbol)
            print(f"   Warning: 'Symbol' column not found for {index_name}. Inspecting DataFrame...")
            print(df.head())
            return []

        print(f"-> Successfully fetched {len(symbols)} symbols for {index_name}.")
        return symbols

    except requests.exceptions.HTTPError as e:
        print(f"   Error fetching {index_name} (HTTP Error): {e}. URL may be outdated.")
        return []
    except Exception as e:
        print(f"   An unexpected error occurred for {index_name}: {e}")
        return []

# --- Main Execution ---
for name, file in INDEX_MAP.items():
    symbols = get_index_constituents(name, file)
    index_symbols[name] = symbols
    all_symbols.update(symbols)

# --- Display Results ---
print("\n" + "="*50)
print("             NSE Index Constituents Symbols")
print("="*50)

for name, symbols in index_symbols.items():
    print(f"\n--- {name} ({len(symbols)} symbols) ---")
    if symbols:
        # Display the first 5 and last 5 symbols for a clean output
        print(symbols[:5], "...", symbols[-5:])
    else:
        print("List is empty (check for errors above)")

print("\n" + "="*50)
print(f"Total Unique Symbols Found: {len(all_symbols)}")
# print(sorted(list(all_symbols))) # Uncomment to see the full, combined list