import json
import os
import pandas as pd
import pytest
from pathlib import Path
from datetime import datetime

from helpers.datahandler import DataHandler


def write_bhav_csv(path: Path, rows: list):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def test_update_stocks_with_bhavcopy_data_dry_run(tmp_path):
    data_dir = tmp_path / 'data'
    bhav_dir = tmp_path / 'bhav'
    data_dir.mkdir()
    bhav_dir.mkdir()

    dh = DataHandler(data_path=str(data_dir), bhavcopy_path=str(bhav_dir))
    # Ensure mapping exists
    dh.data['all_stocks']['RELIANCE'] = 'RELIANCE_EQ_RELIANCE.csv'
    dh.all_stocks = dh.data['all_stocks']

    bhav_file = bhav_dir / 'cm-sample-bhav.csv'
    today = datetime.now().strftime('%d-%b-%Y')
    rows = [{
        'SYMBOL': 'RELIANCE',
        'SERIES': 'EQ',
        'DATE1': today,
        'OPEN_PRICE': 2300.0,
        'HIGH_PRICE': 2350.0,
        'LOW_PRICE': 2290.0,
        'CLOSE_PRICE': 2335.0,
        'LAST_PRICE': 2335.0,
        'PREV_CLOSE': 2300.0,
        'TTL_TRD_QNTY': 123456,
    }]
    write_bhav_csv(bhav_file, rows)

    # Run dry-run
    assert dh.update_stocks_with_bhavcopy_data(bhav_files=[str(bhav_file)], dry_run=True, symbols=['RELIANCE']) is True

    # Per-symbol CSV should not have been created in dry-run
    expected_file = data_dir / dh.data['all_stocks']['RELIANCE']
    assert not expected_file.exists()

    # A log/JSON report should be created under logs
    logs_dir = Path(dh.bhavcopy_path) / 'logs'
    assert logs_dir.exists()
    reports = list(logs_dir.glob('bhav_ingest_*.json'))
    assert len(reports) >= 1
    rep = json.loads(reports[-1].read_text())
    assert rep['dry_run'] is True
    assert rep['processed_rows'] >= 1
    csv_reports = list(logs_dir.glob('bhav_ingest_*_symbols.csv'))
    assert len(csv_reports) >= 1


def test_update_stocks_with_bhavcopy_data_apply_and_dedupe(tmp_path):
    data_dir = tmp_path / 'data'
    bhav_dir = tmp_path / 'bhav'
    data_dir.mkdir()
    bhav_dir.mkdir()

    dh = DataHandler(data_path=str(data_dir), bhavcopy_path=str(bhav_dir))
    dh.data['all_stocks']['RELIANCE'] = 'RELIANCE_EQ_RELIANCE.csv'
    dh.all_stocks = dh.data['all_stocks']

    # Create an existing per-symbol CSV with one row for 2025-11-21
    existing_file = data_dir / dh.data['all_stocks']['RELIANCE']
    existing_df = pd.DataFrame([{'DATE': '2025-11-21', 'OPEN': 100.0, 'HIGH': 110.0, 'LOW': 90.0, 'CLOSE': 105.0, '52W H': None, '52W L': None, 'SYMBOL': 'RELIANCE'}])
    existing_df.to_csv(existing_file, index=False)

    # Bhav with same date but different OPEN should replace existing in non-dry-run
    bhav_file = bhav_dir / 'cm-test-bhav.csv'
    rows = [{
        'SYMBOL': 'RELIANCE',
        'SERIES': 'EQ',
        'DATE1': '21-Nov-2025',
        'OPEN_PRICE': 200.0,
        'HIGH_PRICE': 210.0,
        'LOW_PRICE': 190.0,
        'CLOSE_PRICE': 205.0,
        'LAST_PRICE': 205.0,
        'PREV_CLOSE': 100.0,
        'TTL_TRD_QNTY': 10,
    }]
    write_bhav_csv(bhav_file, rows)

    assert dh.update_stocks_with_bhavcopy_data(bhav_files=[str(bhav_file)], dry_run=False, symbols=['RELIANCE']) is True

    # After update, the file should exist and OPEN should be 200.0
    assert existing_file.exists()
    df = pd.read_csv(existing_file)
    assert 'DATE' in df.columns
    # The row for 2025-11-21 should exist and reflect new OPEN value 200.0
    row = df.loc[df['DATE'] == '2025-11-21'].iloc[0]
    assert float(row['OPEN']) == 200.0


def test_update_stocks_with_bhavcopy_data_compute_52w(tmp_path):
    data_dir = tmp_path / 'data'
    bhav_dir = tmp_path / 'bhav'
    data_dir.mkdir()
    bhav_dir.mkdir()

    dh = DataHandler(data_path=str(data_dir), bhavcopy_path=str(bhav_dir))
    dh.data['all_stocks']['RELIANCE'] = 'RELIANCE_EQ_RELIANCE.csv'
    dh.all_stocks = dh.data['all_stocks']

    existing_file = data_dir / dh.data['all_stocks']['RELIANCE']
    # existing CSV with two rows
    existing_df = pd.DataFrame([
        {'DATE': '2025-11-20', 'OPEN': 100.0, 'HIGH': 110.0, 'LOW': 90.0, 'CLOSE': 105.0, '52W H': None, '52W L': None, 'SYMBOL': 'RELIANCE'},
        {'DATE': '2025-11-21', 'OPEN': 120.0, 'HIGH': 125.0, 'LOW': 115.0, 'CLOSE': 122.0, '52W H': None, '52W L': None, 'SYMBOL': 'RELIANCE'},
    ])
    existing_df.to_csv(existing_file, index=False)

    bhav_file = bhav_dir / 'cm-test-bhav-52w.csv'
    rows = [{
        'SYMBOL': 'RELIANCE',
        'SERIES': 'EQ',
        'DATE1': '22-Nov-2025',
        'OPEN_PRICE': 130.0,
        'HIGH_PRICE': 135.0,
        'LOW_PRICE': 125.0,
        'CLOSE_PRICE': 132.0,
        'LAST_PRICE': 132.0,
        'PREV_CLOSE': 122.0,
        'TTL_TRD_QNTY': 10,
    }]
    write_bhav_csv(bhav_file, rows)

    assert dh.update_stocks_with_bhavcopy_data(bhav_files=[str(bhav_file)], dry_run=False, symbols=['RELIANCE'], compute_52w=True) is True

    df = pd.read_csv(existing_file)
    # Now '52W H' and '52W L' should be present and computed, at least for the last row
    assert '52W H' in df.columns and '52W L' in df.columns
    # latest row is date 2025-11-22; get its computed 52W H/L
    latest_row = df.loc[df['DATE'] == '2025-11-22'].iloc[0]
    assert float(latest_row['52W H']) == pytest.approx(max(110.0, 125.0, 135.0), rel=1e-3)
    assert float(latest_row['52W L']) == pytest.approx(min(90.0, 115.0, 125.0), rel=1e-3)
