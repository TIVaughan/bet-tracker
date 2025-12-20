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

def get_daily_metrics(bets: List[BetEntry]) -> pd.DataFrame:
    """Calculate daily metrics from bet history."""
    if not bets:
        return pd.DataFrame()
    
    df = pd.DataFrame(bets)
    df['Date'] = pd.to_datetime(df['Date'])
    df['Profit'] = df.apply(
        lambda x: (calculate_payout(x['Odds'], x['Amount']) - x['Amount']) 
        if x['Result'] == 'WIN' else -x['Amount'], 
        axis=1
    )
    
    daily = df.groupby('Date').agg({
        'Profit': 'sum',
        'Amount': 'count'
    }).reset_index()
    
    daily['Cumulative'] = daily['Profit'].cumsum()
    return daily

def plot_daily_performance(closed_bets: List[BetEntry], open_bets: List[BetEntry] = None) -> alt.Chart:
    """Create an area chart showing daily performance."""
    # Process closed bets
    closed_df = get_daily_metrics(closed_bets) if closed_bets else pd.DataFrame()
    
    # Create base chart
    base = alt.Chart(closed_df).encode(
        x=alt.X('Date:T', title='Date'),
        y=alt.Y('Cumulative:Q', title='Cumulative Profit ($)')
    )
    
    if not closed_df.empty:
        # Add closed bets area
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
        )
        
        # Add points for closed bets
        points = base.mark_circle(
            color='#27ae60',
            size=60,
            opacity=1
        ).encode(
            tooltip=[
                alt.Tooltip('Date:T', title='Date'),
                alt.Tooltip('Cumulative:Q', title='Cumulative Profit', format='$.2f'),
                alt.Tooltip('Profit:Q', title='Daily Profit', format='$.2f')
            ]
        )
        
        chart = (closed_area + points).properties(
            height=400,
            title='Daily Betting Performance'
        )
        return chart
    
    return alt.Chart().mark_text(text='No data available')

def main():
    st.set_page_config(page_title="Bet Tracker", page_icon="🎯")
    st.title("Bet Tracker")
    init_state()

    # Add CSV upload in sidebar
    st.sidebar.header("Import Historical Data")
    uploaded_file = st.sidebar.file_uploader(
        "Upload CSV with columns: amount, odds, result, date",
        type=['csv']
    )
    
    if uploaded_file is not None:
        historical_bets = process_csv_upload(uploaded_file)
        if historical_bets:
            st.session_state.history.extend(historical_bets)
            st.sidebar.success(f"Successfully imported {len(historical_bets)} historical bets")
    
    # Bet entry form
    st.write("Enter your bets: **Amount**, **Odds (American)**, and **Result**")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        amount = st.number_input("Amount ($)", min_value=0.0, step=5.0, format="%.2f", value=50.0, key="amount_input")
    with col2:
        odds = st.number_input("Odds (American)", value=-110.0, format="%.0f", key="odds_input")
    with col3:
        result = st.selectbox("Result", options=["+", "-", "Open"], 
                            format_func=lambda s: {"+": "Win (+)", "-": "Loss (-)", "Open": "Open"}.get(s, s), 
                            key="result_input")

    # Buttons
    submit = st.button("Submit Bet", key="submit_btn")
    reset_btn = st.button("Reset All", key="reset_btn")

    if submit:
        if result == "Open":
            # Add to open bets
            bet = {
                "Amount": amount,
                "Odds": odds,
                "Result": "PENDING",
                "Date": datetime.now().date(),
                "Status": "OPEN"
            }
            st.session_state.open_bets.append(bet)
            st.success(f"Added open bet: ${amount:.2f} at {odds} odds")
        else:
            # Add to closed bets
            bet = {
                "Amount": amount,
                "Odds": odds,
                "Result": "WIN" if result == "+" else "LOSS",
                "Date": datetime.now().date(),
                "Status": "CLOSED"
            }
            st.session_state.history.append(bet)
            st.success(f"Added {bet['Result']} bet: ${amount:.2f} at {odds} odds")

    if reset_btn:
        st.session_state.total_position = 0.0
        st.session_state.total_returns = 0.0
        st.session_state.available_credit = 0.0
        st.session_state.history = []
        st.session_state.open_bets = []
        st.success("All bets have been reset!")

    # Display metrics
    st.markdown("---")
    st.header("Summary")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Total Returns", f"${st.session_state.total_returns:.2f}")
    col_b.metric("Total Position", f"${st.session_state.total_position:.2f}")
    col_c.metric("Available Credit", f"${st.session_state.available_credit:.2f}")
    col_d.metric("Open Bets", f"{len(st.session_state.open_bets)}")

    # Add the daily performance chart
    st.markdown("---")
    st.header("Daily Performance")
    chart = plot_daily_performance(
        closed_bets=st.session_state.history,
        open_bets=st.session_state.open_bets
    )
    st.altair_chart(chart, use_container_width=True)

    # Display bet history
    st.markdown("---")
    st.header("Bet History")
    
    # Show open bets
    if st.session_state.open_bets:
        st.subheader("Open Bets")
        open_bets_df = pd.DataFrame(st.session_state.open_bets)
        st.dataframe(open_bets_df, use_container_width=True)
    
    # Show closed bets
    if st.session_state.history:
        st.subheader("Closed Bets")
        history_df = pd.DataFrame(st.session_state.history)
        st.dataframe(history_df, use_container_width=True)
        
        # Add download button
        csv = history_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download History as CSV",
            csv,
            "bet_history.csv",
            "text/csv",
            key='download-csv'
        )
    elif not st.session_state.open_bets:
        st.info("No bets recorded yet. Add bets to see them here.")

if __name__ == "__main__":
    main()