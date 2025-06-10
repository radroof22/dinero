
# %%
import pandas as pd

# %%
fidelity_df = pd.read_csv('portfolio_data/fidelity.csv')
fidelity_df['Source'] = 'Fidelity'
fidelity_df.head()

# %%
# drop rows that have 'NaN' ass account name
fidelity_df = fidelity_df[fidelity_df['Account Name'].notna()]

# %%
# in the rows where quantity is NaN, set the quantity to Current Value
# and set Last Price to 1.00 and Total Cost Basis to Current Value
fidelity_df.loc[fidelity_df['Quantity'].isna(), 'Last Price'] = 1.00
fidelity_df.loc[fidelity_df['Quantity'].isna(), 'Cost Basis Total'] = fidelity_df['Current Value']
fidelity_df.loc[fidelity_df['Quantity'].isna(), 'Quantity'] = fidelity_df['Current Value']

# %%
fidelity_col = {
    "Account Name": "Account Type",
    "Symbol": "Symbol",
    "Description": "Description",
    "Quantity": "Quantity",
    "Last Price": "Current Price",
    "Cost Basis Total": "Cost Basis Total",
    "Source": "Source",
}

fidelity_df = fidelity_df.rename(columns=fidelity_col)
fidelity_df = fidelity_df[fidelity_col.values()]

# %%
# all of the rows where quantity contains '$', replace the $ and , with ''
fidelity_df['Quantity'] = pd.to_numeric(
    fidelity_df['Quantity'].astype(str).str.replace('$', '').str.replace(',', ''), 
    errors='coerce'  # This will convert any non-numeric values to NaN
)
fidelity_df['Current Price'] = pd.to_numeric(
    fidelity_df['Current Price'].astype(str).str.replace('$', '').str.replace(',', ''), 
    errors='coerce'  # This will convert any non-numeric values to NaN
)
fidelity_df['Cost Basis Total'] = pd.to_numeric(
    fidelity_df['Cost Basis Total'].astype(str).str.replace('$', '').str.replace(',', ''), 
    errors='coerce'  # This will convert any non-numeric values to NaN
)

# %%
# load the in the charles_schwab.csv file
# set the header column to the 3rd row
schwab_df = pd.read_csv('portfolio_data/charles_schwab.csv')
schwab_df.columns = schwab_df.iloc[2]
schwab_df['Source'] = 'Charles Schwab'
schwab_df.head()

# %%
# drop rows that have 'NaN' ass account name
schwab_df = schwab_df[schwab_df['Symbol'].notna()]

# %%
# Create Account Type column
schwab_df['Account Type'] = None

# Find rows that contain account type information
account_type_mask = schwab_df['Symbol'].str.contains('Individual|Roth|Contributory', na=False)
schwab_df.loc[account_type_mask, 'Account Type'] = schwab_df.loc[account_type_mask, 'Symbol'].str.extract(r'(Individual|Roth|Contributory.*)', expand=False)

# Forward fill the Account Type to rows below until the next account type
schwab_df['Account Type'] = schwab_df['Account Type'].fillna(method='ffill')

# %% 
# drop the rows with Description column as "NaN" or have "Description" as cell value
schwab_df = schwab_df[schwab_df['Security Type'].notna() & (schwab_df['Security Type'] != "Security Type") & (schwab_df['Security Type'] != "--")]
# if "% of Acct" is NaN, drop the row
schwab_df = schwab_df[schwab_df['% of Acct (% of Account)'].notna()]

# %%
# add description Quantity and Price and Cost Basis for Cash
schwab_df.loc[schwab_df["Symbol"].str.contains("Cash", na=False), "Qty (Quantity)"] = schwab_df.loc[schwab_df["Symbol"].str.contains("Cash", na=False), "Mkt Val (Market Value)"]
schwab_df.loc[schwab_df["Symbol"].str.contains("Cash", na=False), "Cost Basis"] = schwab_df.loc[schwab_df["Symbol"].str.contains("Cash", na=False), "Qty (Quantity)"]
schwab_df.loc[schwab_df["Symbol"].str.contains("Cash", na=False), "Price"] = 1.0


# %%
# rename columns to match fidelity_df
schwab_col = {
    "Account Type": "Account Type",
    "Symbol": "Symbol",
    "Description": "Description",
    "Qty (Quantity)": "Quantity",
    "Price": "Current Price",
    "Cost Basis": "Cost Basis Total",
    "Source": "Source",
}
schwab_df = schwab_df.rename(columns=schwab_col)
schwab_df = schwab_df[schwab_col.values()]

# %%
# convert Quantity to numeric and Current Price + Cost Basis Total
# the rows containin "$NUMBER" are strings, so we need to remove the $ and ,
# all of the rows where quantity contains '$', replace the $ and , with ''
schwab_df['Quantity'] = pd.to_numeric(
    schwab_df['Quantity'].astype(str).str.replace('$', '').str.replace(',', ''), 
    errors='coerce'  # This will convert any non-numeric values to NaN
)
schwab_df['Current Price'] = pd.to_numeric(
    schwab_df['Current Price'].astype(str).str.replace('$', '').str.replace(',', ''), 
    errors='coerce'  # This will convert any non-numeric values to NaN
)
schwab_df['Cost Basis Total'] = pd.to_numeric(
    schwab_df['Cost Basis Total'].astype(str).str.replace('$', '').str.replace(',', ''), 
    errors='coerce'  # This will convert any non-numeric values to NaN
)

# %%
portfolio_df = pd.concat([fidelity_df, schwab_df])
# %%
# Normalize the account type names
portfolio_df.loc[portfolio_df['Account Type'].str.contains('Individual', na=False), 'Account Type'] = 'Brokerage'
portfolio_df.loc[portfolio_df['Account Type'].str.contains('Roth', na=False), 'Account Type'] = 'Roth IRA'

portfolio_df.loc[portfolio_df['Account Type'].str.contains('ROTH', na=False), 'Account Type'] = 'Roth IRA'
portfolio_df.loc[portfolio_df['Account Type'].str.contains('Contributory|Traditional', na=False), 'Account Type'] = 'Traditional IRA'


# %%
portfolio_df["Position Value"] = portfolio_df["Quantity"] * portfolio_df["Current Price"]
portfolio_df["Cost Basis per Share"] = portfolio_df["Cost Basis Total"] / portfolio_df["Quantity"]
portfolio_df["PnL"] = (portfolio_df["Position Value"] - portfolio_df["Cost Basis Total"]) / portfolio_df["Cost Basis Total"]

# %%
# create dataframe that normalizes the rows by Symbol. SO if two rows have same symbol the Cost Basis Total is the sum of the Cost Basis Total
# and the Quantity is the sum of the Quantity. Copy the "Current Price" from the first row
portfolio_df_normalized = portfolio_df.groupby('Symbol').agg({
    'Cost Basis Total': 'sum',
    'Quantity': 'sum',
    'Current Price': 'first'
}).reset_index()

portfolio_df_normalized["Position Value"] = portfolio_df_normalized["Quantity"] * portfolio_df_normalized["Current Price"]
portfolio_df_normalized["Cost Basis per Share"] = portfolio_df_normalized["Cost Basis Total"] / portfolio_df_normalized["Quantity"]
portfolio_df_normalized["PnL"] = (portfolio_df_normalized["Position Value"] - portfolio_df_normalized["Cost Basis Total"]) / portfolio_df_normalized["Cost Basis Total"]

# %%
import matplotlib.pyplot as plt
import numpy as np

# graph of Symbol versus PnL
plt.figure(figsize=(12, 6))

# Create colors based on PnL values
pnl_values = portfolio_df_normalized['PnL'] * 100
colors = ['red' if x < 0 else 'green' if x > 0 else 'white' for x in pnl_values]
# Create gradient effect by adjusting alpha based on magnitude
alphas = np.abs(pnl_values/max(abs(pnl_values)))
colors = [plt.matplotlib.colors.to_rgba(c, alpha=a) for c, a in zip(colors, alphas)]

plt.bar(portfolio_df_normalized['Symbol'], pnl_values, color=colors)
plt.xticks(rotation=45, ha='right')
plt.ylabel('Profit/Loss (%)')
plt.title('Profit/Loss by Symbol')
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()
plt.show()


# %%
# make a pie chart visualizing Weightage of each Symbol in the portfolio
plt.figure(figsize=(12, 6))
plt.pie(portfolio_df_normalized['Position Value'], labels=portfolio_df_normalized['Symbol'], autopct='%1.1f%%')
plt.title('Weightage of each Symbol in the portfolio')
plt.show()

# %%
# Calculate total cash and invested amounts
cash_amount = portfolio_df_normalized[portfolio_df_normalized['Current Price'] == 1.00]['Position Value'].sum()
invested_amount = portfolio_df_normalized[portfolio_df_normalized['Current Price'] != 1.00]['Position Value'].sum()

# Create pie chart
plt.figure(figsize=(10, 6))
plt.pie([invested_amount, cash_amount], 
        labels=['Invested', 'Cash'],
        autopct='%1.1f%%',
        colors=['#2ecc71', '#3498db'])
plt.title('Portfolio Distribution: Invested vs Cash')
plt.show()

# %%
# total portfolio value
# Calculate total cost basis and portfolio value
total_cost_basis = portfolio_df_normalized['Cost Basis Total'].sum()
total_portfolio_value = portfolio_df_normalized['Position Value'].sum()

print(f"Total Cost Basis: ${total_cost_basis:,.2f}")
print(f"Total Portfolio Value: ${total_portfolio_value:,.2f}")
print(f"Total Amount Invested: ${invested_amount:,.2f}")
print(f"Total Cash: ${cash_amount:,.2f}")

# %%
