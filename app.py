# Add these imports at the top of the file
import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from typing import List, Dict, Any
import numpy as np

# Update the BetEntry type to include a date
BetEntry = Dict[str, Any]

def calculate_payout(odds: float, amount: float) -> float:
    """Calculate total payout (stake + profit) for American odds."""
    if odds > 0:
        return amount + (odds / 100.0) * amount
    else:
        return amount + (100.0 / abs(odds)) * amount

def init_state():
    st.session_state.setdefault("total_position", 0.0)
    st.session_state.setdefault("total_returns", 0.0)
    st.session_state.setdefault("available_credit", 0.0)
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("open_bets", [])  # Track open bets separately

def process_csv_upload(uploaded_file) -> List[BetEntry]:
    """Process uploaded CSV file and return list of bet entries."""
    try:
        # Define the date format in the CSV
        date_format = "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)"
        
        # Read CSV with explicit date parsing
        df = pd.read_csv(
            uploaded_file,
            parse_dates=['date'],
            date_parser=lambda x: pd.to_datetime(x, format=date_format)
        )
        
        # Ensure required columns exist
        required_columns = ['date', 'amount_usd', 'price', 'outcome', 'outcome_amount']
        if not all(col in df.columns for col in required_columns):
            st.error(f"CSV must contain columns: {', '.join(required_columns)}")
            return []
        
        bets = []
        for _, row in df.iterrows():
            # Skip rows with no outcome (pending bets)
            if pd.isna(row['outcome']):
                continue
                
            # Determine result (win/loss) and profit/loss
            result = "WIN" if str(row['outcome']).strip().lower() == 'win' else "LOSS"
            if result == "WIN":
                profit = float(row['outcome_amount']) - float(row['amount_usd'])
                payout = float(row['outcome_amount'])
            else:
                profit = -float(row['amount_usd'])
                payout = 0.0
                
            bet = {
                "Date": row['date'].date(),
                "Amount": float(row['amount_usd']),
                "Odds": float(row['price']),
                "Result": result,
                "Payout": round(payout, 2),
                "Profit": round(profit, 2),
                "Player": str(row.get('player', '')),
                "Team": str(row.get('team', '')),
                "Position": str(row.get('position', '')),
                "Line": str(row.get('line', '')),
                "BetType": str(row.get('transaction_type', '')),
                "Status": "CLOSED"
            }
            bets.append(bet)
        return bets
    except Exception as e:
        st.error(f"Error processing CSV: {str(e)}")
        return []

def get_daily_metrics(bets: List[BetEntry], month_to_date: bool = True) -> pd.DataFrame:
    """Calculate daily metrics from bet history.
    
    Args:
        bets: List of bet entries
        month_to_date: If True, only include data from the current month
    """
    if not bets:
        return pd.DataFrame()
    
    df = pd.DataFrame(bets)
    
    # Convert Date to datetime if it's not already
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        df['Date'] = pd.to_datetime(df['Date'])
    
    # Filter for current month if month_to_date is True
    if month_to_date:
        current_month = pd.Timestamp.now().replace(day=1)
        df = df[df['Date'] >= current_month]
    
    # Calculate profit for each bet
    df['Profit'] = df.apply(
        lambda x: x['Payout'] - x['Amount'] if x['Result'] == 'WIN' else -x['Amount'],
        axis=1
    )
    
    # Group by date and calculate metrics
    daily = df.groupby('Date').agg({
        'Profit': 'sum',
        'Amount': 'sum'
    }).reset_index()
    
    # Calculate running total
    daily['Cumulative'] = daily['Profit'].cumsum()
    
    return daily

def plot_daily_performance(closed_bets: List[BetEntry], open_bets: List[BetEntry] = None) -> alt.Chart:
    """Create an area chart showing daily performance."""
    # Process closed bets for current month
    closed_df = get_daily_metrics(closed_bets, month_to_date=True)
    
    # Process open bets for current month
    open_df = get_daily_metrics(open_bets, month_to_date=True) if open_bets else pd.DataFrame()
    
    # Create base chart
    base = alt.Chart().encode(
        x=alt.X('Date:T', title='Date'),
        y=alt.Y('Cumulative:Q', title='Cumulative Profit ($)')
    )
    
    charts = []
    
    # Add closed bets area if we have data
    if not closed_df.empty:
        closed_area = base.mark_area(
            color='#2ecc71',
            opacity=0.8,
            interpolate='monotone'
        ).encode(
            tooltip=[
                alt.Tooltip('Date:T', title='Date'),
                alt.Tooltip('Cumulative:Q', title='Cumulative Profit', format='$.2f'),
                alt.Tooltip('Profit:Q', title='Daily Profit', format='$.2f')
            ]
        ).transform_filter(alt.datum.Cumulative != 0)
        
        closed_points = base.mark_circle(
            color='#27ae60',
            size=60,
            opacity=1
        ).encode(
            tooltip=[
                alt.Tooltip('Date:T', title='Date'),
                alt.Tooltip('Cumulative:Q', title='Cumulative Profit', format='$.2f'),
                alt.Tooltip('Profit:Q', title='Daily Profit', format='$.2f')
            ]
        ).transform_filter(alt.datum.Cumulative != 0)
        
        charts.extend([closed_area, closed_points])
    
    # Add open bets area if we have data
    if not open_df.empty:
        open_area = base.mark_area(
            color='#3498db',
            opacity=0.4,
            interpolate='monotone'
        ).encode(
            tooltip=[
                alt.Tooltip('Date:T', title='Date'),
                alt.Tooltip('Cumulative:Q', title='Potential Cumulative', format='$.2f'),
                alt.Tooltip('Profit:Q', title='Potential Daily', format='$.2f')
            ]
        ).transform_filter(alt.datum.Cumulative != 0)
        
        open_points = base.mark_triangle(
            color='#2980b9',
            size=100,
            opacity=0.8
        ).encode(
            tooltip=[
                alt.Tooltip('Date:T', title='Date'),
                alt.Tooltip('Cumulative:Q', title='Potential Cumulative', format='$.2f'),
                alt.Tooltip('Profit:Q', title='Potential Daily', format='$.2f')
            ]
        ).transform_filter(alt.datum.Cumulative != 0)
        
        charts.extend([open_area, open_points])
    
    if charts:
        # Use the appropriate dataframe (prefer closed_df if available)
        data = closed_df if not closed_df.empty else open_df
        chart = alt.layer(*charts, data=data).properties(
            height=400,
            title='Monthly Performance (MTD)'
        )
        return chart
    
    return alt.Chart().mark_text(text='No data available for current month')

def main():
    st.set_page_config(page_title="Bet Tracker", page_icon="🎯")
    st.title("Bet Tracker")
    init_state()

    # Add CSV upload in sidebar
    st.sidebar.header("Import Betting Data")
    uploaded_file = st.sidebar.file_uploader(
        "Upload Betting CSV",
        type=['csv']
    )
    
    if uploaded_file is not None:
        historical_bets = process_csv_upload(uploaded_file)
        if historical_bets:
            st.session_state.history.extend(historical_bets)
            st.sidebar.success(f"Successfully imported {len(historical_bets)} bets")
            
            # Debug: Show first few bets
            st.sidebar.write("First 3 imported bets:")
            for i, bet in enumerate(historical_bets[:3]):
                st.sidebar.json({k: str(v) for k, v in bet.items()})

    # Calculate metrics
    closed_bets = [b for b in st.session_state.history if b.get('Status') == 'CLOSED']
    open_bets = [b for b in st.session_state.history if b.get('Status') == 'OPEN']

    # Debug: Show counts
    st.sidebar.write(f"Total bets: {len(st.session_state.history)}")
    st.sidebar.write(f"Closed bets: {len(closed_bets)}")
    st.sidebar.write(f"Open bets: {len(open_bets)}")

    # Get current month's data
    current_month = pd.Timestamp.now().replace(day=1).date()
    st.sidebar.write(f"Current month: {current_month}")

    # Convert dates to datetime.date objects if they're strings
    def parse_date(date_val):
        if date_val is None:
            return None
        try:
            if isinstance(date_val, str):
                return pd.to_datetime(date_val).date()
            elif hasattr(date_val, 'date'):
                return date_val.date()
            elif hasattr(date_val, 'to_pydatetime'):
                return date_val.to_pydatetime().date()
            return date_val
        except Exception as e:
            st.sidebar.error(f"Error parsing date {date_val}: {str(e)}")
            return None

    # Filter for current month's closed bets
    mtd_closed = []
    for bet in closed_bets:
        bet_date = parse_date(bet.get('Date'))
        st.sidebar.write(f"Bet date: {bet_date} (type: {type(bet_date)})")
        if bet_date is None:
            continue
            
        # Convert to date if it's a datetime
        if hasattr(bet_date, 'date'):
            bet_date = bet_date.date()
            
        # Compare dates directly
        if isinstance(bet_date, datetim

    # Calculate metrics with proper type handling
    total_returns = 0.0
    for bet in mtd_closed:
        try:
            profit = float(bet.get('Profit', 0))
            st.sidebar.write(f"Bet profit: {profit} (type: {type(profit)})")
            total_returns += profit
        except (TypeError, ValueError) as e:
            st.sidebar.error(f"Error processing profit for bet: {e}")

    total_position = 0.0
    for bet in open_bets:
        try:
            amount = float(bet.get('Amount', 0))
            st.sidebar.write(f"Open bet amount: {amount} (type: {type(amount)})")
            total_position += amount
        except (TypeError, ValueError) as e:
            st.sidebar.error(f"Error processing amount for open bet: {e}")

    st.sidebar.write(f"Calculated total_returns: {total_returns}")
    st.sidebar.write(f"Calculated total_position: {total_position}")

    # Display metrics
    st.markdown("---")
    st.header("Month to Date Summary")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Returns", f"${total_returns:,.2f}")
    with col2:
        st.metric("Active Position", f"${total_position:,.2f}")
    with col3:
        st.metric("Open Bets", len(open_bets))

    # Rest of your code remains the same...

if __name__ == "__main__":
    main()