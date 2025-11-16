"""
Table Display Helper Module
============================

This module provides utilities for displaying pandas DataFrames as styled tables
in Jupyter notebooks with multiple visualization options.

Functions:
-----------
1. display_table_styled() - Color-coded HTML table (recommended)
2. display_table_simple() - Plain text table (quick overview)
3. display_table_plotly() - Interactive Plotly table
4. display_table_summary_stats() - Summary statistics
5. display_table_comparison() - Compare two DataFrames
6. display_table_filtered() - Show filtered data

Example:
--------
from helpers.table_display import display_table_styled, display_table_simple
import pandas as pd

df = pd.DataFrame({'Stock': ['RELIANCE', 'TCS'], 'Win%': [0.65, 0.72]})
display_table_styled(df, title="Backtest Results")
display_table_simple(df, title="Quick View")
"""

import pandas as pd
import numpy as np
from IPython.display import HTML, display
import plotly.graph_objects as go


def display_table_styled(df, title="Results", height=400, max_rows=None, highlight_cols=None):
    """
    Display DataFrame as a styled HTML table with color formatting.
    
    Best for: Professional reports, color-coded performance metrics
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe to display
    title : str
        Title of the table
    height : int
        Height of the table container in pixels
    max_rows : int or None
        Maximum rows to display (None = all)
    highlight_cols : list or None
        List of column names to highlight with gradient colors
        Default: Auto-detects performance metrics (win%, ROI, wins)
    
    Example:
    --------
    display_table_styled(results_df, title="Backtest Results", max_rows=10)
    """
    # Limit rows if specified
    display_df = df.head(max_rows) if max_rows else df
    
    # Create styled DataFrame
    styled = display_df.style
    
    # Auto-detect columns to highlight
    if highlight_cols is None:
        numeric_cols = display_df.select_dtypes(include=[np.number]).columns
        highlight_cols = [col for col in numeric_cols if col in ['win%', 'ROI', 'wins', 'gain%']]
    
    # Apply color gradients to specified columns
    for col in highlight_cols:
        if col in display_df.columns:
            styled = styled.background_gradient(
                subset=[col],
                cmap='RdYlGn',
                vmin=display_df[col].min(),
                vmax=display_df[col].max()
            )
    
    # Format numeric columns
    numeric_cols = display_df.select_dtypes(include=[np.number]).columns
    format_dict = {}
    
    for col in numeric_cols:
        if col in ['win%', 'ROI', 'gain%']:
            format_dict[col] = '{:.2f}%'
        elif col in ['days', 'wins', 'losses', 'buys', 'sells', 'hold_period', 'trades']:
            format_dict[col] = '{:.0f}'
        else:
            format_dict[col] = '{:.2f}'
    
    styled = styled.format(format_dict)
    styled = styled.set_properties(**{'text-align': 'center', 'font-size': '11pt'})
    styled = styled.set_table_styles([
        {'selector': 'th', 'props': [('background-color', '#4472C4'), ('color', 'white'), ('font-weight', 'bold')]},
        {'selector': 'tr:hover', 'props': [('background-color', '#E7E6E6')]},
    ])
    
    print(f"\n{'='*80}\n📊 {title}\n{'='*80}\n")
    display(styled)
    print(f"\n📈 Summary: {len(display_df)} results displayed out of {len(df)} total\n")
    
    return styled


def display_table_simple(df, title="Results", max_rows=15):
    """
    Display DataFrame as a simple text table.
    
    Best for: Quick overview, terminal-friendly output
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe to display
    title : str
        Title of the table
    max_rows : int
        Maximum rows to display
    
    Example:
    --------
    display_table_simple(results_df, title="Quick Summary", max_rows=10)
    """
    display_df = df.head(max_rows) if max_rows else df
    
    print(f"\n{'='*100}")
    print(f"📊 {title}")
    print(f"{'='*100}\n")
    print(display_df.to_string())
    print(f"\n{'='*100}")
    print(f"📈 Total Results: {len(df)} | Displayed: {len(display_df)}")
    print(f"{'='*100}\n")


def display_table_plotly(df, title="Results", max_rows=10, height=None):
    """
    Display DataFrame as an interactive Plotly table.
    
    Best for: Presentations, interactive exploration
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe to display
    title : str
        Title of the table
    max_rows : int
        Maximum rows to display
    height : int or None
        Height of the table (auto-calculated if None)
    
    Example:
    --------
    display_table_plotly(results_df, title="Interactive Results", max_rows=10)
    """
    display_df = df.head(max_rows) if max_rows else df
    
    # Reset index to include stock names as a column
    df_reset = display_df.reset_index()
    df_reset.columns = ['Stock'] + list(df_reset.columns[1:])
    
    # Auto-calculate height if not specified
    if height is None:
        height = max(400, len(df_reset) * 30 + 100)
    
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(df_reset.columns),
            fill_color='#4472C4',
            align='center',
            font=dict(color='white', size=12, family='Arial')
        ),
        cells=dict(
            values=[df_reset[col].values for col in df_reset.columns],
            fill_color=['white']*len(df_reset.columns),
            align='center',
            font=dict(size=11),
            height=25
        )
    )])
    
    fig.update_layout(
        title=f"<b>{title}</b><br><sub>Total: {len(df)} results | Showing: {len(display_df)}</sub>",
        height=height,
        margin=dict(l=0, r=0, t=50, b=0),
        font=dict(family='Arial', size=11)
    )
    
    fig.show()


def display_table_summary_stats(df, title="Results"):
    """
    Display summary statistics of DataFrame.
    
    Best for: High-level overview, key metrics
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe to summarize
    title : str
        Title of the summary
    
    Example:
    --------
    display_table_summary_stats(results_df, title="Backtest Summary")
    """
    print(f"\n{'='*80}")
    print(f"📊 {title} - SUMMARY STATISTICS")
    print(f"{'='*80}\n")
    
    # Count statistics
    print(f"Total Entries:              {len(df)}")
    
    # If it looks like backtest results
    if 'win%' in df.columns:
        print(f"Average Win%:               {df['win%'].mean():.2%}")
        print(f"Best Win%:                  {df['win%'].max():.2%} ({df['win%'].idxmax()})")
        print(f"Worst Win%:                 {df['win%'].min():.2%} ({df['win%'].idxmin()})")
    
    if 'ROI' in df.columns:
        print(f"Average ROI:                {df['ROI'].mean():.2f}%")
        print(f"Best ROI:                   {df['ROI'].max():.2f}% ({df['ROI'].idxmax()})")
    
    if 'wins' in df.columns:
        print(f"Average Wins per Entry:     {df['wins'].mean():.2f}")
    
    if 'losses' in df.columns:
        print(f"Average Losses per Entry:   {df['losses'].mean():.2f}")
    
    if 'hold_period' in df.columns:
        hold_periods = df['hold_period'].apply(lambda x: np.mean(x) if isinstance(x, (list, tuple)) else x)
        print(f"Average Hold Period (days): {hold_periods.mean():.1f}")
    
    # Performance tiers
    if 'win%' in df.columns:
        print(f"\nPerformance Tiers:")
        print(f"  >50% Win Rate:            {len(df[df['win%'] > 0.50])}")
        print(f"  >60% Win Rate:            {len(df[df['win%'] > 0.60])}")
        print(f"  >70% Win Rate:            {len(df[df['win%'] > 0.70])}")
        print(f"  100% Win Rate:            {len(df[df['win%'] == 1.00])}")
    
    print(f"\n{'='*80}\n")


def display_table_comparison(df1, df2, title1="Dataset 1", title2="Dataset 2"):
    """
    Display two DataFrames side-by-side for comparison.
    
    Best for: Comparing strategy results, before/after comparisons
    
    Parameters:
    -----------
    df1 : pandas.DataFrame
        First dataframe to compare
    df2 : pandas.DataFrame
        Second dataframe to compare
    title1 : str
        Title for first dataset
    title2 : str
        Title for second dataset
    
    Example:
    --------
    display_table_comparison(macd_results, rsi_results, "MACD Strategy", "RSI Strategy")
    """
    print(f"\n{'='*100}")
    print(f"📊 COMPARISON VIEW")
    print(f"{'='*100}\n")
    
    print(f"✅ {title1}:")
    display_table_simple(df1, title=title1, max_rows=5)
    
    print(f"\n{'='*100}\n")
    
    print(f"✅ {title2}:")
    display_table_simple(df2, title=title2, max_rows=5)


def display_table_filtered(df, filter_col, min_val=None, max_val=None, title="Filtered Results"):
    """
    Display filtered view of DataFrame based on column value range.
    
    Best for: Focusing on specific performance ranges
    
    Parameters:
    -----------
    df : pandas.DataFrame
        The dataframe to filter
    filter_col : str
        Column name to filter on
    min_val : float or None
        Minimum value (inclusive)
    max_val : float or None
        Maximum value (inclusive)
    title : str
        Title of the filtered view
    
    Example:
    --------
    display_table_filtered(results_df, 'win%', min_val=0.60, title="Stocks with >60% Win Rate")
    """
    # Apply filters
    filtered_df = df.copy()
    
    if min_val is not None:
        filtered_df = filtered_df[filtered_df[filter_col] >= min_val]
    
    if max_val is not None:
        filtered_df = filtered_df[filtered_df[filter_col] <= max_val]
    
    print(f"\n{'='*80}")
    print(f"🔍 {title}")
    print(f"{'='*80}\n")
    print(f"Filter: {filter_col}")
    if min_val is not None:
        print(f"  Min: {min_val}")
    if max_val is not None:
        print(f"  Max: {max_val}")
    print(f"\nResults: {len(filtered_df)} out of {len(df)} entries\n")
    
    display_table_styled(filtered_df, title=title)


def format_currency(value, prefix='₹'):
    """Format value as currency."""
    return f"{prefix}{value:,.2f}"


def format_percentage(value, decimals=2):
    """Format value as percentage."""
    return f"{value:.{decimals}%}"


def create_summary_dict(df, title="Summary"):
    """
    Create a summary statistics dictionary from DataFrame.
    
    Returns:
    --------
    dict : Dictionary with summary statistics
    """
    summary = {
        'Title': title,
        'Total Count': len(df),
        'Column Count': len(df.columns),
        'Numeric Columns': len(df.select_dtypes(include=[np.number]).columns),
    }
    
    # Add statistics for numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        summary[f'{col}_mean'] = df[col].mean()
        summary[f'{col}_max'] = df[col].max()
        summary[f'{col}_min'] = df[col].min()
    
    return summary


# Quick preset display functions
def show_best_performers(df, metric='win%', top_n=10):
    """Quick function to show top N performers."""
    top = df.nlargest(top_n, metric)
    display_table_styled(top, title=f"🏆 Top {top_n} by {metric}", max_rows=top_n)


def show_worst_performers(df, metric='win%', top_n=10):
    """Quick function to show worst N performers."""
    bottom = df.nsmallest(top_n, metric)
    display_table_styled(bottom, title=f"📉 Bottom {top_n} by {metric}", max_rows=top_n)


def show_all_stats(df, title="Complete Analysis"):
    """Show all statistics in one view."""
    print(f"\n{'='*100}")
    print(f"📊 COMPREHENSIVE ANALYSIS: {title}")
    print(f"{'='*100}\n")
    
    display_table_styled(df, title="Full Dataset")
    display_table_summary_stats(df, title)
    show_best_performers(df)
    show_worst_performers(df)


if __name__ == "__main__":
    # Example usage
    print("Table Display Helper Module")
    print("Import this module in your Jupyter notebook:")
    print("  from helpers.table_display import display_table_styled, display_table_simple")
