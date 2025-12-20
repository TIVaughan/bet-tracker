# Add these imports at the top of the file
from datetime import datetime
import io
from typing import List, Dict, Any
import numpy as np

# Update the BetEntry type to include a date
BetEntry = Dict[str, Any]

def init_state():
    st.session_state.setdefault("total_position", 0.0)
    st.session_state.setdefault("total_returns", 0.0)
    st.session_state.setdefault("available_credit", 0.0)
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("open_bets", [])  # Track open bets separately

def process_csv_upload(uploaded_file) -> List[BetEntry]:
    """Process uploaded CSV file and return list of bet entries."""
    try:
        df = pd.read_csv(uploaded_file)
        # Ensure required columns exist
        required_columns = ['amount', 'odds', 'result', 'date']
        if not all(col in df.columns for col in required_columns):
            st.error(f"CSV must contain columns: {', '.join(required_columns)}")
            return []
        
        bets = []
        for _, row in df.iterrows():
            bet = {
                "Amount": float(row['amount']),
                "Odds": float(row['odds']),
                "Result": "WIN" if str(row['result']).strip().upper() in ['WIN', 'W', '1', 'TRUE'] else "LOSS",
                "Date": pd.to_datetime(row['date']).date(),
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
    if not closed_df.empty:
        base = alt.Chart(closed_df).encode(
            x=alt.X('Date:T', title='Date'),
            y=alt.Y('Cumulative:Q', title='Cumulative Profit ($)')
        )
        
        # Add closed bets area
        closed_area = base.mark_area(
            color='#2ecc71',
            opacity=0.8,
            line={'color': '#27ae60'}
        ).encode(
            tooltip=[
                alt.Tooltip('Date:T', title='Date'),
                alt.Tooltip('Cumulative:Q', title='Cumulative Profit', format='$.2f'),
                alt.Tooltip('Profit:Q', title='Daily Profit', format='$.2f')
            ]
        )
        
        # Add points for each data point
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

# In the main function, add these UI elements before the bet entry form:
def main():
    # ... existing imports and setup ...
    
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
    
    # ... rest of the existing main function ...

    # Add the daily performance chart after the potential outcomes section
    if st.session_state.history:
        st.markdown("---")
        st.header("Daily Performance")
        chart = plot_daily_performance(
            closed_bets=[b for b in st.session_state.history if b.get('Status') == 'CLOSED'],
            open_bets=[b for b in st.session_state.history if b.get('Status') != 'CLOSED']
        )
        st.altair_chart(chart, use_container_width=True)