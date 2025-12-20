# app.py
import streamlit as st
import pandas as pd
import altair as alt


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
    st.session_state.setdefault("total_position", 0.0)
    st.session_state.setdefault("total_returns", 0.0)
    st.session_state.setdefault("available_credit", 0.0)
    st.session_state.setdefault("history", [])

def reset_all():
    st.session_state.total_position = 0.0
    st.session_state.total_returns = 0.0
    st.session_state.available_credit = 0.0
    st.session_state.history = []
    st.success("All bets have been reset!")

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

def calculate_win_percentage() -> float:
    """Calculate win percentage from bet history."""
    if not st.session_state.history:
        return 0.0
    wins = sum(1 for b in st.session_state.history if b["Result"] == "WIN")
    total = len(st.session_state.history)
    return (wins / total) * 100

def calculate_potential_outcomes():
    """Calculate total potential winnings and losses."""
    total_loss = 0.0
    total_win = 0.0

    for bet in st.session_state.history:
        total_loss += bet["Amount"]

        if bet["Odds"] > 0:
            profit = (bet["Odds"] / 100.0) * bet["Amount"]
        else:
            profit = (100.0 / abs(bet["Odds"])) * bet["Amount"]

        total_win += profit

    return round(total_win, 2), round(total_loss, 2)


# ----------------------------
# Main app
# ----------------------------
def main():
    st.set_page_config(page_title="Bet Tracker", page_icon="🎯")
    st.title("Bet Tracker")
    init_state()

    st.write("Enter your bets: **Amount**, **Odds (American)**, and **Result (+ for win, - for loss)**")

    # Input fields with unique keys
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        amount = st.number_input("Amount ($)", min_value=0.0, step=5.0, format="%.2f", value=50.0, key="amount_input")
    with col2:
        odds = st.number_input("Odds (American)", value=-110.0, format="%.0f", key="odds_input")
    with col3:
        result = st.selectbox("Result", options=["+", "-"], format_func=lambda s: "Win (+)" if s == "+" else "Loss (-)", key="result_input")

    # Buttons
    submit = st.button("Submit Bet", key="submit_btn")
    reset_btn = st.button("Reset All", key="reset_btn")

    if submit:
        record_bet(amount=float(amount), odds=float(odds), result=result)

    if reset_btn:
        reset_all()

    # Display metrics
    st.markdown("---")
    st.header("Summary")
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Total Returns", f"${st.session_state.total_returns:.2f}")
    col_b.metric("Total Position", f"${st.session_state.total_position:.2f}")
    col_c.metric("Available Credit", f"${st.session_state.available_credit:.2f}")
    col_d.metric("Win %", f"{calculate_win_percentage():.2f}%")

    st.markdown("---")
    st.header("Potential Outcomes")

if st.session_state.history:
    potential_win, potential_loss = calculate_potential_outcomes()

    chart_data = pd.DataFrame({
        "Type": ["Potential Winnings", "Potential Losses"],
        "Amount": [potential_win, -potential_loss]  # losses are negative
    })

    chart = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X("Amount:Q", title="Amount ($)", axis=alt.Axis(format="$")),
            y=alt.Y("Type:N", sort=None, title=None),
            color=alt.Color(
                "Amount:Q",
                scale=alt.Scale(
                    domain=[-max(potential_loss, potential_win), max(potential_loss, potential_win)],
                    range=["#ff4d4d", "#2ecc71"]
                ),
                legend=None
            )
        )
        .properties(height=120)
    )

    st.altair_chart(chart, use_container_width=True)

    st.caption(
        f"Max upside: **${potential_win:.2f}** | "
        f"Max downside: **-${potential_loss:.2f}**"
    )
else:
    st.info("Add bets to see potential winnings and losses.")



    # Display bet history in a container
    st.markdown("---")
    st.header("Bet History")
    if st.session_state.history:
        # Header
        header_cols = st.columns([1,1,1,1,1,0.5])
        header_cols[0].write("Amount")
        header_cols[1].write("Odds")
        header_cols[2].write("Result")
        header_cols[3].write("Payout")
        header_cols[4].write("Profit")
        header_cols[5].write("🗑️")

        # Track rows to delete
        rows_to_delete = []

        for i, bet in enumerate(st.session_state.history):
            row_cols = st.columns([1,1,1,1,1,0.5])
            row_cols[0].write(f"${bet['Amount']:.2f}")
            row_cols[1].write(f"{bet['Odds']}")
            row_cols[2].write(f"{bet['Result']}")
            row_cols[3].write(f"${bet['Payout']:.2f}")
            row_cols[4].write(f"${bet['Profit']:.2f}")

            if row_cols[5].button("🗑️", key=f"delete_{i}"):
                rows_to_delete.append(i)

        # Delete rows in reverse order to not break indices
        if rows_to_delete:
            for i in reversed(rows_to_delete):
                bet = st.session_state.history.pop(i)
                st.session_state.total_position -= bet["Amount"]
                st.session_state.total_returns -= bet["Profit"]
                st.session_state.available_credit -= bet["Payout"]
                st.info(f"Removed bet: {bet['Result']} of ${bet['Amount']:.2f}")

        # CSV download
        df = pd.DataFrame(st.session_state.history)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download History CSV", csv, "bet_history.csv", "text/csv")
    else:
        st.info("No bets recorded yet.")

if __name__ == "__main__":
    main()
