# %%
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import yfinance as yf

st.set_page_config(page_title="Portfolio Dashboard", layout="wide")

# -----------------------------
# USER CONFIGURATION SECTION
# -----------------------------
# List CSV files to load.  Update this list to point to any number of files.
CSV_FILES = [
    "portfolio_data/fidelity.csv",
    "portfolio_data/charles_schwab.csv",
]
# -----------------------------

st.title("📈 Personal Portfolio Dashboard")

@st.cache_data(show_spinner=False)
def load_fidelity(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Tag source & drop useless rows
    df["Source"] = "Fidelity"
    df = df[df["Account Name"].notna()]

    # Treat cash rows (Quantity NaN) like positions at $1.00
    cash_rows = df["Quantity"].isna()
    df.loc[cash_rows, "Last Price"] = 1.0
    df.loc[cash_rows, "Cost Basis Total"] = df.loc[cash_rows, "Current Value"]
    df.loc[cash_rows, "Quantity"] = df.loc[cash_rows, "Current Value"]

    # Standardise columns
    keep = {
        "Account Name": "Account Type",
        "Symbol": "Symbol",
        "Description": "Description",
        "Quantity": "Quantity",
        "Last Price": "Current Price",
        "Cost Basis Total": "Cost Basis Total",
        "Source": "Source",
    }
    df = df.rename(columns=keep)[keep.values()]

    # Numeric cleanup
    for col in ["Quantity", "Current Price", "Cost Basis Total"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace("$", "").str.replace(",", ""), errors="coerce"
        )

    # Derive nicer account type labels
    df["Account Type"] = df["Account Type"].str.extract(
        r"(Individual|ROTH IRA|Traditional IRA)", expand=False
    )
    df["Account Type"] = df["Account Type"].replace(
        {"Individual": "Brokerage", "ROTH IRA": "Roth IRA"}
    )
    return df

@st.cache_data(show_spinner=False)
def load_schwab(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path, header=None)
    raw.columns = raw.iloc[3]  # third row contains headers
    df = raw.copy()
    df = df[df["Symbol"].notna()]  # drop empty rows
    df["Source"] = "Charles Schwab"

    # Build Account Type column
    df["Account Type"] = None
    acct_mask = df["Symbol"].str.contains("Individual|Roth|Contributory", na=False)
    df.loc[acct_mask, "Account Type"] = df.loc[acct_mask, "Symbol"].str.extract(
        r"(Individual|Roth|Contributory.*)", expand=False
    )
    df["Account Type"] = df["Account Type"].fillna(method="ffill")

    # Remove non-holding rows
    df = df[
        df["Security Type"].notna()
        & (df["Security Type"] != "Security Type")
        & (df["Security Type"] != "--")
    ]
    df = df[df["% of Acct (% of Account)"].notna()]

    # Treat cash rows
    cash_mask = df["Symbol"].str.contains("Cash", na=False)
    df.loc[cash_mask, "Qty (Quantity)"] = df.loc[cash_mask, "Mkt Val (Market Value)"]
    df.loc[cash_mask, "Cost Basis"] = df.loc[cash_mask, "Qty (Quantity)"]
    df.loc[cash_mask, "Price"] = 1.0

    keep = {
        "Account Type": "Account Type",
        "Symbol": "Symbol",
        "Description": "Description",
        "Qty (Quantity)": "Quantity",
        "Price": "Current Price",
        "Cost Basis": "Cost Basis Total",
        "Source": "Source",
    }
    df = df.rename(columns=keep)[keep.values()]

    # Numeric cleanup
    for col in ["Quantity", "Current Price", "Cost Basis Total"]:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace("$", "").str.replace(",", ""), errors="coerce"
        )

    # Normalize account type labels
    df["Account Type"] = df["Account Type"].replace(
        {
            r".*Individual.*": "Brokerage",
            r".*Roth.*": "Roth IRA",
            r".*Contributory.*|.*Traditional.*": "Traditional IRA",
        },
        regex=True,
    )
    return df

# -----------------------------
# LOAD & PROCESS DATA
# -----------------------------
portfolio_frames = []
for fp in CSV_FILES:
    if "fidelity" in fp.lower():
        portfolio_frames.append(load_fidelity(fp))
    elif "schwab" in fp.lower():
        portfolio_frames.append(load_schwab(fp))
    else:
        st.warning(f"Unrecognised broker for file: {fp}. Skipping.")

if not portfolio_frames:
    st.error("No valid data loaded. Please check CSV_FILES list.")
    st.stop()

portfolio_df = pd.concat(portfolio_frames, ignore_index=True)

# -------------------------------------------------
# UPDATE PRICES WITH YAHOO FINANCE
# -------------------------------------------------

@st.cache_data(show_spinner="Fetching latest prices from Yahoo Finance …")
def fetch_latest_prices(symbols: list[str]) -> dict[str, float]:
    """Return a mapping of symbol → latest market price using yfinance.

    Falls back to the last close if real-time quote is unavailable.
    """
    prices: dict[str, float] = {}
    for sym in symbols:
        if sym.upper() == "CASH":  # skip literal cash symbol just in case
            continue
        try:
            ticker = yf.Ticker(sym)
            price = ticker.fast_info.get("last_price") if hasattr(ticker, "fast_info") else None
            if price is None:
                price = ticker.info.get("regularMarketPrice")
            if price is None:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            if price is not None and price > 0:
                prices[sym] = price
        except Exception:
            # ignore individual fetch errors and continue
            continue
    return prices

# Map live prices (skip cash rows where price == 1.0)
live_price_map = fetch_latest_prices(portfolio_df["Symbol"].unique().tolist())
non_cash_mask = portfolio_df["Current Price"] != 1.0
portfolio_df.loc[non_cash_mask, "Current Price"] = portfolio_df.loc[non_cash_mask, "Symbol"].map(live_price_map).fillna(
    portfolio_df.loc[non_cash_mask, "Current Price"]
)

# -------------------------------------------------
# FETCH DIVIDEND DATA
# -------------------------------------------------

@st.cache_data(show_spinner="Fetching dividend data …")
def fetch_dividends(symbols: list[str]) -> dict[str, float]:
    """Return a mapping of symbol → annual dividend per share (USD).

    Attempts to use forward dividend; falls back to trailing dividend rate.
    """
    dividends: dict[str, float] = {}
    for sym in symbols:
        if sym.upper() == "CASH":
            dividends[sym] = 0.0
            continue
        try:
            ticker = yf.Ticker(sym)
            div = None
            # Forward dividend
            div = ticker.info.get("dividendRate") if ticker.info else None
            if div is None:
                # Trailing annual dividend
                div = ticker.info.get("trailingAnnualDividendRate") if ticker.info else None
            if div is not None and div >= 0:
                dividends[sym] = float(div)
        except Exception:
            continue
    return dividends

# Attach dividend per share to portfolio_df (0 if unavailable)
div_map = fetch_dividends(portfolio_df["Symbol"].unique().tolist())
portfolio_df["Dividend"] = portfolio_df["Symbol"].map(div_map).fillna(0.0)

# Derived columns (recalculate with latest prices)
portfolio_df["Position Value"] = portfolio_df["Quantity"] * portfolio_df["Current Price"]
portfolio_df["Cost Basis per Share"] = portfolio_df["Cost Basis Total"] / portfolio_df["Quantity"]
portfolio_df["PnL"] = (
    portfolio_df["Position Value"] - portfolio_df["Cost Basis Total"]
) / portfolio_df["Cost Basis Total"]

# Normalised view (group by symbol)
portfolio_norm = (
    portfolio_df.groupby("Symbol")
    .agg({
        "Cost Basis Total": "sum",
        "Quantity": "sum",
        "Current Price": "first",
        "Dividend": "first",
    })
    .reset_index()
)
portfolio_norm["Position Value"] = portfolio_norm["Quantity"] * portfolio_norm["Current Price"]
portfolio_norm["Cost Basis per Share"] = portfolio_norm["Cost Basis Total"] / portfolio_norm["Quantity"]
portfolio_norm["PnL"] = (
    portfolio_norm["Position Value"] - portfolio_norm["Cost Basis Total"]
) / portfolio_norm["Cost Basis Total"]

# Adjusted Yield (Dividend per share divided by cost basis per share)
portfolio_norm["Adjusted Yield"] = (
    portfolio_norm["Dividend"] / portfolio_norm["Cost Basis per Share"]
).replace([np.inf, -np.inf], np.nan)

# CASH / INVESTED SUMMARY
cash_value = portfolio_norm[portfolio_norm["Current Price"] == 1.0]["Position Value"].sum()
invested_value = portfolio_norm[portfolio_norm["Current Price"] != 1.0]["Position Value"].sum()

# ---------------------------------
# LAYOUT
# ---------------------------------

st.header("Raw Positions")
# Format price columns with $ and 2 decimal points, PnL as percentage
display_df = portfolio_df.copy()
display_df['Current Price'] = display_df['Current Price'].apply(lambda x: f'${x:,.2f}')
display_df['Dividend'] = display_df['Dividend'].apply(lambda x: f'${x:,.2f}')
display_df['Current Dividend Yield'] = (portfolio_df['Dividend'].astype(float) / portfolio_df['Current Price'].astype(float)).apply(lambda x: f'{x*100:,.2f}%')
display_df['Cost Basis per Share'] = display_df['Cost Basis per Share'].apply(lambda x: f'${x:,.2f}')
display_df['Cost Basis Total'] = display_df['Cost Basis Total'].apply(lambda x: f'${x:,.2f}')
display_df['Position Value'] = display_df['Position Value'].apply(lambda x: f'${x:,.2f}')
display_df['PnL'] = display_df['PnL'].apply(lambda x: f'{x*100:.2f}%')
st.dataframe(display_df, height=300)

# ----- NORMALISED (SYMBOL-LEVEL) TABLE -----
st.subheader("Normalized Positions (Aggregated by Symbol)")

# Prepare a nicely formatted version of portfolio_norm
display_norm = portfolio_norm.copy()
for col in ["Current Price", "Cost Basis per Share"]:
    display_norm[col] = display_norm[col].apply(lambda x: f"${x:,.2f}")
for col in ["Cost Basis Total", "Position Value"]:
    display_norm[col] = display_norm[col].apply(lambda x: f"${x:,.2f}")
display_norm["Dividend"] = display_norm["Dividend"].apply(lambda x: f"${x:,.2f}")
display_norm["PnL"] = display_norm["PnL"].apply(lambda x: f"{x*100:.2f}%")
display_norm["Current Dividend Yield"] = (portfolio_norm["Dividend"] / portfolio_norm["Current Price"]).apply(lambda x: f"{x*100:.2f}%")

display_norm["Adjusted Yield"] = display_norm["Adjusted Yield"].apply(lambda x: f"{(x or 0)*100:.2f}%" if pd.notna(x) else "-")

st.dataframe(display_norm, height=300)

# ----- BAR CHART: PnL -----
with st.container():
    st.subheader("Profit / Loss by Symbol (%)")
    pnl_pct = portfolio_norm["PnL"] * 100
    # Build gradient colours (red→white→green) with alpha proportional to magnitude
    max_abs = pnl_pct.abs().max() or 1
    bar_colors = []
    for v in pnl_pct:
        if np.isnan(v):
            bar_colors.append("rgba(255,255,255,0)")
            continue
        alpha = min(abs(v) / max_abs, 1)
        if v < 0:
            bar_colors.append(f"rgba(255,0,0,{alpha})")  # red shades
        elif v > 0:
            bar_colors.append(f"rgba(0,128,0,{alpha})")  # green shades
        else:
            bar_colors.append("rgba(255,255,255,1)")

    fig_bar = go.Figure(
        data=[
            go.Bar(
                x=portfolio_norm["Symbol"],
                y=pnl_pct,
                marker_color=bar_colors,
            )
        ]
    )
    fig_bar.update_layout(
        yaxis_title="Profit / Loss (%)",
        xaxis_title="",
        xaxis_tickangle=-45,
        template="plotly_white",
        height=400,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ----- PIE CHARTS -----
col1, col2 = st.columns(2)

with col1:
    st.subheader("Portfolio Weight by Value")
    fig_val = px.pie(
        portfolio_norm,
        values="Position Value",
        names="Symbol",
        hole=0.4,
    )
    fig_val.update_layout(height=400)
    st.plotly_chart(fig_val, use_container_width=True)

with col2:
    st.subheader("Portfolio Weight by Cost Basis")
    fig_cb = px.pie(
        portfolio_norm,
        values="Cost Basis Total",
        names="Symbol",
        hole=0.4,
    )
    fig_cb.update_layout(height=400)
    st.plotly_chart(fig_cb, use_container_width=True)

# ----- INVESTED VS CASH & CASH BY ACCOUNT -----
col_ic, col_ca = st.columns(2)

# Pie: Invested vs Cash
with col_ic:
    st.subheader("Invested vs Cash (Current Value)")
    fig_ic = px.pie(
        names=["Invested", "Cash"],
        values=[invested_value, cash_value],
        color=["Invested", "Cash"],
        color_discrete_map={"Invested": "#2ecc71", "Cash": "#3498db"},
        hole=0.4,
    )
    fig_ic.update_layout(height=400)
    st.plotly_chart(fig_ic, use_container_width=True)

# Bar: Cash by Account (Account Type + Source)
with col_ca:
    st.subheader("Cash by Account")
    cash_df = (
        portfolio_df[portfolio_df["Current Price"] == 1.0]
        .groupby(["Account Type", "Source"], as_index=False)["Position Value"].sum()
    )
    cash_df["Account"] = cash_df["Account Type"] + " - " + cash_df["Source"]

    # If there is no cash in any account, avoid empty plot
    if cash_df.empty:
        st.info("No cash positions detected across accounts.")
    else:
        fig_cash = px.bar(
            cash_df,
            x="Account",
            y="Position Value",
            color="Position Value",
            color_continuous_scale="Oranges",
        )
        fig_cash.update_layout(
            yaxis_title="Cash ($)",
            xaxis_title="",
            xaxis_tickangle=-45,
            height=400,
            template="plotly_white",
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_cash, use_container_width=True)

# ----- KPI METRICS -----
col_a, col_b = st.columns(2)
col_a.metric("Total Cash ($)", f"{cash_value:,.2f}")
col_b.metric("Total Portfolio Value ($)", f"{invested_value + cash_value:,.2f}")

# ----- FILE INFORMATION -----
st.subheader("Data Sources")
file_info = []
for fp in CSV_FILES:
    path = Path(fp)
    if path.exists():
        # Use modification time instead of creation time for cross-platform compatibility
        mod_time = pd.Timestamp.fromtimestamp(path.stat().st_mtime)
        file_info.append({
            "File": path.name,
            "Last Modified": mod_time.strftime("%Y-%m-%d %H:%M:%S"),
            "Size": f"{path.stat().st_size / 1024:.1f} KB"
        })
st.table(pd.DataFrame(file_info))

st.caption("All calculations are based on the latest CSV exports provided.")

# %%
