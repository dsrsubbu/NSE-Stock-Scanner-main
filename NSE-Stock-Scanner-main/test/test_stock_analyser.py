import pandas as pd
import numpy as np
from helpers.stock_analyser import AnalyseStocks


def make_sample_df():
    # Create a small DataFrame with expected columns and 5 rows
    dates = pd.date_range(end=pd.Timestamp.today(), periods=5)
    df = pd.DataFrame({
        'DATE': dates.strftime('%Y-%m-%d'),
        'OPEN': np.linspace(100, 104, 5),
        'CLOSE': np.linspace(101, 105, 5),
        'LOW': np.linspace(99, 103, 5),
        'HIGH': np.linspace(102, 106, 5),
        'SYMBOL': ['TST'] * 5
    })
    return df


def test_get_recent_info_atomic(monkeypatch):
    analyser = AnalyseStocks(check_fresh=False)

    sample_df = make_sample_df()

    # Monkeypatch methods to return deterministic results and avoid IO
    monkeypatch.setattr(analyser, 'open_downloaded_stock', lambda name: sample_df)
    monkeypatch.setattr(analyser, 'get_index', lambda name: 'Nifty 50')
    monkeypatch.setattr(analyser, 'macd_signal', lambda df: 'No Signal')
    monkeypatch.setattr(analyser, 'get_CCI', lambda df, signal_only=True: 'No Signal')
    # _recent_info returns: 0..9 indices including RSI at 4 and rest of values
    monkeypatch.setattr(analyser, '_recent_info', lambda name, **kwargs: (100, 200, 300, 400, 'No Signal', 3, 1, 0, 2, 5))

    # Should not raise and lengths should match
    df = analyser.get_recent_info(nifty=200, custom_list=['TST'], **{'mvs':[20,50,100,200]})
    assert not df.empty
    assert len(df['Name']) == len(df.index)
    # All arrays/columns should have equal length
    lengths = [len(df[col]) for col in df.columns]
    assert len(set(lengths)) == 1


def test_ichi_count_short_df():
    analyser = AnalyseStocks(check_fresh=False)
    # Prepare a DataFrame with fewer than 27 rows
    dates = pd.date_range(end=pd.Timestamp.today(), periods=5)
    df = pd.DataFrame({
        'DATE': dates.strftime('%Y-%m-%d'),
        'OPEN': np.linspace(100, 104, 5),
        'CLOSE': np.linspace(101, 105, 5),
        'LOW': np.linspace(99, 103, 5),
        'HIGH': np.linspace(102, 106, 5),
        'blue_line': np.linspace(100, 104, 5),
        'red_line': np.linspace(99, 103, 5),
        'cloud_green_line_a': np.linspace(98, 102, 5),
        'cloud_red_line_b': np.linspace(97, 101, 5),
        'lagging_line': np.linspace(100, 104, 5),
    })
    # Ensure Ichi_count returns an integer and doesn't raise
    count = analyser.Ichi_count(df)
    assert isinstance(count, int)
