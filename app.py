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

    # Get current month's data
    current_month = pd.Timestamp.now().replace(day=1).date()
    st.sidebar.write(f"Current month: {current_month} (type: {type(current_month)})")

    # Convert dates and filter for current month
    mtd_closed = []
    for bet in closed_bets:
        try:
            bet_date = bet.get('Date')
            if isinstance(bet_date, str):
                bet_date = pd.to_datetime(bet_date).date()
            elif hasattr(bet_date, 'date'):
                bet_date = bet_date.date()
            
            st.sidebar.write(f"Processing bet date: {bet_date} (type: {type(bet_date)})")
            
            if bet_date and bet_date >= current_month:
                mtd_closed.append(bet)
        except Exception as e:
            st.sidebar.error(f"Error processing bet date {bet.get('Date')}: {e}")

    # Calculate metrics
    total_returns = sum(float(b.get('Profit', 0)) for b in mtd_closed)
    total_position = sum(float(b.get('Amount', 0)) for b in open_bets)

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

    # Add the chart
    st.markdown("---")
    st.header("Monthly Performance")
    if mtd_closed or open_bets:
        chart = plot_daily_performance(
            closed_bets=mtd_closed,
            open_bets=open_bets
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No data available for the current month")

    # Display bet history
    st.markdown("---")
    st.header("Bet History")
    
    # Show open bets
    if open_bets:
        st.subheader(f"Open Bets ({len(open_bets)})")
        open_bets_df = pd.DataFrame(open_bets)
        st.dataframe(
            open_bets_df[['Date', 'Player', 'Team', 'BetType', 'Line', 'Amount', 'Odds']],
            use_container_width=True
        )
    
    # Show closed bets
    if closed_bets:
        st.subheader(f"Closed Bets ({len(closed_bets)})")
        closed_bets_df = pd.DataFrame(closed_bets)
        st.dataframe(
            closed_bets_df[['Date', 'Player', 'Team', 'BetType', 'Line', 'Amount', 'Odds', 'Result', 'Profit']],
            use_container_width=True
        )
        
        # Add download button
        csv = closed_bets_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download History as CSV",
            csv,
            "bet_history.csv",
            "text/csv",
            key='download-csv'
        )
    elif not open_bets:
        st.info("No bets recorded yet. Upload a CSV to get started.")

if __name__ == "__main__":
    main()