import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="GreenSupply Electronics Dashboard", layout="wide")

DATA_FILE = "data.xlsx"  # your Excel file (renamed)


@st.cache_data
def load_data():
    orders = pd.read_excel(DATA_FILE, sheet_name="Orders")
    inv = pd.read_excel(DATA_FILE, sheet_name="Inventory")
    inv["Warehouse"] = inv["Warehouse"].astype(str).str.strip()
    # One row in the Inventory sheet has a blank warehouse. It sits in the
    # Barcelona block, and your pivot counts it as Barcelona, so we do too.
    inv.loc[inv["Warehouse"] == "", "Warehouse"] = "Barcelona"
    return orders, inv


orders, inv = load_data()

# ---------- Sidebar filters (these replace your Excel slicers) ----------
st.sidebar.header("Filters")


def pick(label, col):
    options = sorted(orders[col].unique())
    return st.sidebar.multiselect(label, options, default=options)


wh = pick("Warehouse", "Warehouse")
cat = pick("Product Category", "Product Category")
car = pick("Carrier", "Carrier")

df = orders[
    orders["Warehouse"].isin(wh)
    & orders["Product Category"].isin(cat)
    & orders["Carrier"].isin(car)
]
inv_f = inv[inv["Warehouse"].isin(wh) & inv["Product Category"].isin(cat)]

st.title("GreenSupply Electronics Dashboard")
st.caption(f"Data: {orders.shape[0]:,} orders × {orders.shape[1]} columns | {orders['Order Date'].min():%d %b %Y} to {orders['Order Date'].max():%d %b %Y} | {orders['Warehouse'].nunique()} warehouses, {orders['Carrier'].nunique()} carriers, {orders['Product Category'].nunique()} product categories")

if df.empty:
    st.warning("No data for these filters. Please select at least one option in each filter.")
    st.stop()

# ---------- KPIs (same formulas as your pivot tables) ----------
rev = df["Revenue (€)"].sum()
npm = df["Profit Adjusted"].sum() / rev
aov = df["Revenue (€)"].mean()
ontime = df["On Time"].mean()
ret_rate = df["Returned Quantity"].sum() / df["Sales Quantity"].sum()
co2 = df["Estimated Transport Emissions (kg CO₂e)"].sum() / df["Sales Quantity"].sum()

fault = df[df["Return Reason"] == "Product fault"].groupby("Product Category")["Returned Quantity"].sum()
fault_idx = fault / fault.sum() if fault.sum() > 0 else fault
top_fault = fault_idx.idxmax() if len(fault_idx) else "-"

k = st.columns(6)
k[0].metric(" Net Profit Margin", f"{npm:.0%}")
k[1].metric("Average order value", f"€{aov:,.2f}")
k[2].metric("On-time delivery", f"{ontime:.2%}")
k[3].metric("Return rate", f"{ret_rate:.2%}")
k[4].metric("kg CO₂e per unit", f"{co2:.2f}")
k[5].metric(
    "Product fault index",
    f"{fault_idx.max():.1%}" if len(fault_idx) else "-",
    help=f"Share of 'Product fault' returns from the top category: {top_fault}",
)

st.divider()

# ---------- Row 1 ----------
c1, c2 = st.columns(2)

with c1:
    g = df.groupby("Warehouse").agg(rev=("Revenue (€)", "sum"), prof=("Profit Adjusted", "sum")).reset_index()
    g["margin"] = g["prof"] / g["rev"]
    fig = go.Figure()
    fig.add_bar(x=g["Warehouse"], y=g["rev"], name="Revenue (€)", texttemplate="€%{y:.3s}", textposition="outside")
    fig.add_bar(x=g["Warehouse"], y=g["prof"], name="Profit adjusted (€)", texttemplate="€%{y:.3s}", textposition="outside")
    fig.add_scatter(x=g["Warehouse"], y=g["margin"], name="Net profit margin", yaxis="y2", mode="lines+markers+text", texttemplate="%{y:.1%}", textposition="top center")
    fig.update_layout(
        title="Net profit by warehouse",
        barmode="group",
        yaxis=dict(title="€"),
        yaxis2=dict(title="Margin", overlaying="y", side="right", tickformat=".0%", showgrid=False),
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, width='stretch')

with c2:
    g = df.groupby(["Customer Segment", "Customer Region"])["Revenue (€)"].mean().reset_index()
    fig = px.bar(
        g, y="Customer Segment", x="Revenue (€)", color="Customer Region",
        barmode="group", orientation="h", title="Average order value by customer segment", text_auto=",.0f",
    )
    st.plotly_chart(fig, width='stretch')

# ---------- Row 2 ----------
c3, c4 = st.columns(2)

with c3:
    g = df.groupby(["Carrier", "Order Priority"])["On Time"].mean().reset_index()
    fig = px.bar(
        g, x="Carrier", y="On Time", color="Order Priority", barmode="group",
        category_orders={"Order Priority": ["High", "Medium", "Low"]},
        title="On-time delivery % by carrier and priority", text_auto=".1%",
    )
    fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, width='stretch')

with c4:
    g = df.groupby("Carrier").agg(r=("Returned Quantity", "sum"), q=("Sales Quantity", "sum")).reset_index()
    g["Return rate"] = g["r"] / g["q"]
    g = g.sort_values("Return rate")
    fig = px.bar(g, y="Carrier", x="Return rate", orientation="h", title="Return rate by carrier", text_auto=".2%")
    fig.update_xaxes(tickformat=".1%")
    st.plotly_chart(fig, width='stretch')

# ---------- Row 3 ----------
c5, c6 = st.columns(2)

with c5:
    g = df.groupby("Carrier").agg(e=("Estimated Transport Emissions (kg CO₂e)", "sum"), q=("Sales Quantity", "sum")).reset_index()
    g["kg CO₂e per unit"] = g["e"] / g["q"]
    fig = px.bar(g, x="Carrier", y="kg CO₂e per unit", title="Emissions per unit by carrier", text_auto=".3f")
    st.plotly_chart(fig, width='stretch')

with c6:
    if len(fault_idx):
        fi = fault_idx.reset_index()
        fi.columns = ["Product Category", "Fault index"]
        fig = px.pie(fi, names="Product Category", values="Fault index", title="Product fault returns by category")
        fig.update_traces(textinfo="percent+label")
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No 'Product fault' returns for these filters.")

with st.expander("See the data"):
    st.dataframe(df, width='stretch')
