"""yfinance helper utilities for fetching OHLCV at different intervals.

This module provides lightweight fetch functions used by the screening code
to obtain weekly and monthly OHLCV for shortlisted symbols.

Functions provided:
 - fetch_ohlcv()
 - fetch_weekly_ohlc()
 - fetch_monthly_ohlc()

The simple caching layer stores recent responses on disk to avoid repeated
network calls when experimenting locally.
"""

from pathlib import Path
import logging
import pandas as pd
import warnings
import yfinance as yf

LOG = logging.getLogger(__name__)

# Small on-disk cache (CSV) to avoid hammering Yahoo while iterating locally
DEFAULT_CACHE_DIR = Path(__file__).parent / '.cache'
DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _normalize_symbol_for_yahoo(symbol: str) -> str:
	"""Return a Yahoo-friendly symbol. For NSE we add '.NS' when missing."""
	if not isinstance(symbol, str):
		raise TypeError("symbol must be a string")
	symbol = symbol.strip().upper()
	# Keep symbol as-is if it already contains an exchange suffix
	if '.' not in symbol:
		symbol = f"{symbol}.NS"
	return symbol


def _maybe_localize_index(df: pd.DataFrame) -> pd.DataFrame:
	# yfinance returns tz-naive times. Make them UTC to keep parity with
	# the rest of the analyzer which uses tz-aware UTC timestamps.
	if df is None or df.empty:
		return df
	if df.index.tz is None:
		try:
			df.index = df.index.tz_localize('UTC')
		except Exception:
			# If the index can't be localized (e.g., non-datetime), just return
			LOG.debug('Unable to tz_localize index; leaving as-is')
	return df


def _cache_path_for(symbol: str, period: str, interval: str, cache_dir: Path):
	safe_name = symbol.replace('/', '_')
	filename = f"{safe_name}__{period}__{interval}.csv"
	return cache_dir / filename


def fetch_ohlcv(symbol: str, period: str = "1y", interval: str = "1d", *, use_cache: bool = True, cache_dir: Path | str | None = None) -> pd.DataFrame:
	"""Fetch OHLCV using yfinance and return a pandas DataFrame.

	Parameters
	- symbol: ticker name, optionally already including exchange suffix (e.g. 'TCS.NS')
	- period: human-friendly period pased to yfinance (e.g. '1y', '5y')
	- interval: yfinance interval (e.g. '1d', '1wk', '1mo')
	- use_cache: save/load a CSV copy to cache_dir to speed local iterations
	- cache_dir: where to store cached CSVs (defaults to helpers/.cache)

	Returns a DataFrame or None on failure.
	"""
	if cache_dir is None:
		cache_dir = DEFAULT_CACHE_DIR
	else:
		cache_dir = Path(cache_dir)
		cache_dir.mkdir(parents=True, exist_ok=True)

	yahoo_sym = _normalize_symbol_for_yahoo(symbol)
	cache_path = _cache_path_for(yahoo_sym, period, interval, cache_dir)

	# Try to read from cache first
	if use_cache and cache_path.exists():
		try:
			# Read CSV without a custom parser (pandas deprecated `date_parser`)
			# then convert the index to tz-aware datetime explicitly.
			df = pd.read_csv(cache_path, index_col=0)

			# Try a strict ISO format parse first (we write caches using
			# '%Y-%m-%d %H:%M:%S%z'). If that yields NaT values, fall back to
			# flexible parsing so we don't fail on older cache files.
			idx_strict = pd.to_datetime(
				df.index.astype(str), utc=True, format='%Y-%m-%d %H:%M:%S%z', errors='coerce'
			)

			# If strict parse worked for all rows, use it.
			if not idx_strict.isnull().any():
				df.index = idx_strict
			else:
				# Try a flexible parse (slower). Suppress pandas UserWarning
				# about falling back to dateutil; if the flexible parse
				# succeeds for all rows, rewrite the cache into the strict
				# canonical format so subsequent reads parse without fallback.
				with warnings.catch_warnings():
					warnings.simplefilter("ignore", UserWarning)
					idx_fallback = pd.to_datetime(df.index.astype(str), utc=True, errors='coerce')

				if not idx_fallback.isnull().any():
					df.index = idx_fallback
					try:
						# rewrite cache in canonical format to avoid future
						# fallback parsing and warnings
						df.to_csv(cache_path, date_format='%Y-%m-%d %H:%M:%S%z')
						LOG.debug('Normalized cache timestamps for %s at %s', yahoo_sym, cache_path)
					except Exception:
						LOG.debug('Failed to rewrite cache %s after normalization', cache_path)

			# ensure tz-aware
			df = _maybe_localize_index(df)
			LOG.debug('Loaded %s from cache %s', yahoo_sym, cache_path)
			return df
		except Exception:
			LOG.debug('Failed to load cache %s for %s', cache_path, yahoo_sym)

	try:
		# set auto_adjust explicitly to avoid future warnings about the default
		df = yf.download(yahoo_sym, period=period, interval=interval, progress=False, auto_adjust=True)
	except Exception as exc:
		LOG.warning('yfinance request failed for %s (%s): %s', yahoo_sym, interval, exc)
		return None

	if df is None or df.empty:
		LOG.debug('No data returned from yfinance for %s (%s/%s)', yahoo_sym, period, interval)
		return None

	# ensure the index is datetime and timezone-aware (UTC)
	df = _maybe_localize_index(df)

	# Save cache copy for quick re-use
	if use_cache:
		try:
			# write with explicit date format including timezone so reads are consistent
			df.to_csv(cache_path, date_format='%Y-%m-%d %H:%M:%S%z')
		except Exception:
			LOG.debug('Failed to write cache %s', cache_path)

	return df


def fetch_weekly_ohlc(symbol: str, period: str = "1y", *, use_cache: bool = True, cache_dir: Path | str | None = None) -> pd.DataFrame:
	"""Fetch weekly OHLCV for the symbol."""
	return fetch_ohlcv(symbol, period=period, interval='1wk', use_cache=use_cache, cache_dir=cache_dir)


def fetch_monthly_ohlc(symbol: str, period: str = "5y", *, use_cache: bool = True, cache_dir: Path | str | None = None) -> pd.DataFrame:
	"""Fetch monthly OHLCV for the symbol."""
	return fetch_ohlcv(symbol, period=period, interval='1mo', use_cache=use_cache, cache_dir=cache_dir)


if __name__ == '__main__':
	# quick local demo when running this file directly
	import sys
	logging.basicConfig(level=logging.INFO)
	symbol = sys.argv[1] if len(sys.argv) > 1 else 'TATASTEEL'
	print('Weekly:')
	print(fetch_weekly_ohlc(symbol).tail())
	print('\nMonthly:')
	print(fetch_monthly_ohlc(symbol).tail())