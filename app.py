# app.py
import streamlit as st
import pandas as pd

# ----------------------------
# Helper functions
# ----------------------------
def calculate_payout(odds: float, amount: float) -> float:
    """Calculate total payout (stake + profit) for American odds."""
    if odds > 0:
        return amount + (odds / 100.0) * amount
    else:
        return amount + (100.0 / abs(odds)) * amount

def init_state():
    st.session_state.setdefault("total_position", 0.0)      # total amount wagered
    st.session_state.setdefault("total_returns", 0.0)       # net profit/loss
    st.session_state.setdefault("available_credit", 0.0)    # current money pool
    st.session_state.setdefault("history", [])              # list of all bets

def reset_all():
    st.session_state.total_position = 0.0
    st.session_state.total_returns = 0.0
    st.session_state.available_credit = 0.0
    st.session_state.history = []

def record_bet(amount: float, odds: float, result: str):
    """Update state based on a single bet entry."""
    st.session_state.total_position += amount

    if result == "+":
        payout = calculate_payout(odds, amount)
        profit = payout - amount
        st.session_state.total_returns += profit
        st.session_state.available_credit += payout
        entry = {
            "Amount": amount,
            "Odds": odds,
            "Result": "WIN",
            "Payout": round(payout, 2),
            "Profit": round(profit, 2)
        }
        st.success(f"Win recorded: Profit ${profit:.2f}, Payout ${payout:.2f}")
    else:
        st.session_state.total_returns -= amount
        st.session_state.available_credit -= amount
        entry = {
            "Amount": amount,
            "Odds": odds,
            "Result": "LOSS",
            "Payout": 0.0,
            "Profit": -round(amount, 2)
        }
        st.warning(f"Loss recorded: Lost ${amount:.2f}")

    st.session_state.history.append(entry)

# ----------------------------
# Main app
# ----------------------------
def main():
    st.set_page_config(page_title="Bet Tracker", page_icon="🎯")
    st.title("Bet Tracker")
    init_state()

    st.write("Enter your bets: **Amount**, **Odds (American)**, and **Result (+ for win, - for loss)**")

    # Input fields
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        amount = st.number_input("Amount ($)", min_value=0.0, step=5.0, format="%.2f", value=50.0)
    with col2:
        odds = st.number_input("Odds (American)", value=-110.0, format="%.0f")
    with col3:
        result = st.selectbox("Result", options=["+", "-"], format_func=lambda s: "Win (+)" if s == "+" else "Loss (-)")

    # Buttons
    submit = st.button("Submit Bet")
    reset_btn = st.button("Reset All")

    if submit:
        record_bet(amount=float(amount), odds=float(odds), result=result)

    if reset_btn:
        reset_all()
        st.experimental_rerun()

    # Display metrics
    st.markdown("---")
    st.header("Summary")
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Returns", f"${st.session_state.total_returns:.2f}")
    col_b.metric("Total Position", f"${st.session_state.total_position:.2f}")
    col_c.metric("Available Credit", f"${st.session_state.available_credit:.2f}")

    # Display history table
    st.markdown("---")
    st.header("Bet History")
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df, use_container_width=True)
        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download History CSV", csv, "bet_history.csv", "text/csv")
    else:
        st.info("No bets recorded yet.")

if __name__ == "__main__":
    main()


