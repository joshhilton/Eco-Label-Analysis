# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- Configuration ---
st.set_page_config(
    page_title="EU Ecolabel Dashboard",
    page_icon="🇪🇺",
    layout="wide"
)

# --- Data Loading and Caching ---
@st.cache_data # Cache the data loading and cleaning
def load_data(file_path):
    """Loads, cleans, and preprocesses the EU Ecolabel data."""
    try:
        df = pd.read_csv(file_path, sep=';')
        print(f"Initial rows: {len(df)}") # Debug print

        # 1. Remove Complete Duplicates
        initial_rows = len(df)
        df.drop_duplicates(inplace=True)
        print(f"Rows after drop_duplicates: {len(df)}") # Debug print
        if len(df) < initial_rows:
            st.sidebar.info(f"Removed {initial_rows - len(df)} duplicate rows.")

        # 2. Convert 'expiration_date' to datetime
        df['expiration_date'] = pd.to_datetime(df['expiration_date'], errors='coerce')

        # 3. Handle rows where date conversion failed (if any)
        nat_count = df['expiration_date'].isnull().sum()
        if nat_count > 0:
            st.sidebar.warning(f"Removed {nat_count} rows with invalid expiration dates.")
            df.dropna(subset=['expiration_date'], inplace=True)

        # 4. Extract Expiration Year
        # Ensure column is datetime before using .dt accessor
        if pd.api.types.is_datetime64_any_dtype(df['expiration_date']):
            df['expiration_year'] = df['expiration_date'].dt.year.astype(int) # Convert year to integer
        else:
             # Fallback or error handling if date conversion failed unexpectedly
             st.error("Failed to process expiration dates correctly. Cannot extract year.")
             df['expiration_year'] = np.nan # Assign NaN or handle appropriately

        # 5. Convert relevant columns to category for efficiency
        for col in ['product_or_service', 'group_name', 'company_country', 'code_type']:
            if col in df.columns:
                df[col] = df[col].astype('category')

        # 6. Basic check for required columns
        required_cols = ['licence_number', 'company_name', 'company_country', 'group_name', 'expiration_year', 'product_or_service']
        if not all(col in df.columns for col in required_cols):
            st.error(f"Data loading failed. Missing required columns. Found: {df.columns.tolist()}")
            return pd.DataFrame() # Return empty DataFrame

        print(f"Final rows after cleaning: {len(df)}") # Debug print
        return df

    except FileNotFoundError:
        st.error(f"Error: Data file not found at {file_path}")
        return pd.DataFrame() # Return empty DataFrame
    except Exception as e:
        st.error(f"An error occurred during data loading or cleaning: {e}")
        return pd.DataFrame() # Return empty DataFrame

# --- Load Data ---
# Update this path if your file is located elsewhere
file_path = 'eu_ecolabel_data.csv'
df_original = load_data(file_path)

# --- Sidebar Filters ---
st.sidebar.header("Dashboard Filters")

if not df_original.empty:
    # Get unique sorted lists for filters
    # Use .cat.categories for faster unique values from categorical columns
    countries_list = sorted(df_original['company_country'].cat.categories)
    groups_list = sorted(df_original['group_name'].cat.categories)
    min_year, max_year = int(df_original['expiration_year'].min()), int(df_original['expiration_year'].max())

    selected_countries = st.sidebar.multiselect(
        "Company Country",
        options=countries_list,
        default=[] # Default to no selection (all countries)
    )

    selected_groups = st.sidebar.multiselect(
        "Product/Service Group",
        options=groups_list,
        default=[] # Default to no selection (all groups)
    )

    selected_years = st.sidebar.slider(
        "Expiration Year Range",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year) # Default to full range
    )

    # --- Filter Data Based on Sidebar Selection ---
    df_filtered = df_original[
        # If list is empty, condition is True (no filter), otherwise check membership
        (df_original['company_country'].isin(selected_countries) if selected_countries else True) &
        (df_original['group_name'].isin(selected_groups) if selected_groups else True) &
        (df_original['expiration_year'] >= selected_years[0]) &
        (df_original['expiration_year'] <= selected_years[1])
    ].copy() # Use .copy() to avoid SettingWithCopyWarning on potential later modifications

else:
    st.warning("Data could not be loaded. Dashboard cannot be displayed.")
    st.stop() # Stop execution if data loading failed

# --- Main Dashboard Area ---
st.title("🇪🇺 EU Ecolabel Analysis Dashboard")
st.markdown("Exploring the distribution and characteristics of EU Ecolabel licenses.")
st.markdown("---")

# --- Display KPIs ---
if not df_filtered.empty:
    # Calculate KPIs based on unique licenses in the filtered data
    total_unique_licenses = df_filtered['licence_number'].nunique()
    total_unique_companies = df_filtered['company_name'].nunique()
    num_countries = df_filtered['company_country'].nunique()
    num_groups = df_filtered['group_name'].nunique()

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(label="Total Unique Licenses 🏅", value=f"{total_unique_licenses:,}")
    with kpi2:
        st.metric(label="Total Unique Companies 🏢", value=f"{total_unique_companies:,}")
    with kpi3:
        st.metric(label="Countries Represented 🌍", value=f"{num_countries}")
    with kpi4:
        st.metric(label="Product/Service Groups 🏷️", value=f"{num_groups}")
else:
    st.warning("No data matches the current filter criteria.")
    st.stop() # Stop if filters result in no data

st.markdown("---")

# --- Row 1: Geographic and Product Group Overview ---
col1, col2 = st.columns([3, 2]) # Give map more space

with col1:
    st.subheader("🌍 Ecolabels by Company Country")
    if not df_filtered.empty:
        # Aggregate unique licenses per country
        licenses_by_country = df_filtered.groupby('company_country', observed=True)['licence_number'].nunique().reset_index()
        licenses_by_country.rename(columns={'licence_number': 'Unique Licenses'}, inplace=True)

        # Handle potential long country names for mapping if needed (UK example)
        # Simple replacement example (add others if necessary)
        licenses_by_country['company_country'] = licenses_by_country['company_country'].replace(
            'United Kingdom of Great Britain and Northern Ireland', 'United Kingdom'
            )

        # Create Plotly Choropleth map
        fig_map = px.choropleth(
            licenses_by_country,
            locations='company_country',
            locationmode='country names',
            color='Unique Licenses',
            hover_name='company_country',
            hover_data={'Unique Licenses': ':,', 'company_country': False},
            color_continuous_scale=px.colors.sequential.Viridis,
            # scope="europe", # Uncomment to focus map on Europe
            title="Number of Unique Ecolabel Licenses by Company Country Location"
        )
        fig_map.update_layout(margin=dict(l=0, r=0, t=30, b=0)) # Adjust margins
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No data to display map for the current filters.")

with col2:
    st.subheader("🏷️ Top Product Groups")
    if not df_filtered.empty:
        # Aggregate unique licenses per group
        licenses_by_group = df_filtered.groupby('group_name', observed=True)['licence_number'].nunique().reset_index()
        licenses_by_group.rename(columns={'licence_number': 'Unique Licenses'}, inplace=True)
        licenses_by_group = licenses_by_group.sort_values('Unique Licenses', ascending=False).head(15) # Get top 15

        # Create Plotly Bar chart
        fig_group_bar = px.bar(
            licenses_by_group,
            x='Unique Licenses',
            y='group_name',
            orientation='h',
            title="Top 15 Product/Service Groups by Unique Licenses",
            labels={'group_name': 'Product/Service Group', 'Unique Licenses': 'Number of Unique Licenses'},
            text='Unique Licenses' # Show values on bars
        )
        fig_group_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=0, r=0, t=30, b=0))
        fig_group_bar.update_traces(textposition='outside')
        st.plotly_chart(fig_group_bar, use_container_width=True)
    else:
        st.info("No data to display product groups for the current filters.")


st.markdown("---")


# --- Row 2: Temporal and Company Overview ---
col3, col4 = st.columns(2)

with col3:
    st.subheader("📅 License Expiration Trend")
    if not df_filtered.empty:
        # Aggregate unique licenses per expiration year
        licenses_by_year = df_filtered.groupby('expiration_year')['licence_number'].nunique().reset_index()
        licenses_by_year.rename(columns={'licence_number': 'Unique Licenses'}, inplace=True)

        # Create Plotly Bar chart
        fig_year_bar = px.bar(
            licenses_by_year,
            x='expiration_year',
            y='Unique Licenses',
            title="Unique Licenses Expiring by Year",
            labels={'expiration_year': 'Expiration Year', 'Unique Licenses': 'Number of Unique Licenses'},
            text='Unique Licenses'
        )
        fig_year_bar.update_layout(xaxis_type='category', margin=dict(l=0, r=0, t=30, b=0)) # Treat year as category for distinct bars
        fig_year_bar.update_traces(textposition='outside')
        st.plotly_chart(fig_year_bar, use_container_width=True)
    else:
        st.info("No data to display expiration trend for the current filters.")

with col4:
    st.subheader("🏢 Top Companies")
    if not df_filtered.empty:
        # Aggregate unique licenses per company
        licenses_by_company = df_filtered.groupby('company_name')['licence_number'].nunique().reset_index()
        licenses_by_company.rename(columns={'licence_number': 'Unique Licenses'}, inplace=True)
        licenses_by_company = licenses_by_company.sort_values('Unique Licenses', ascending=False).head(15) # Get top 15

        # Create Plotly Bar chart
        fig_company_bar = px.bar(
            licenses_by_company,
            x='Unique Licenses',
            y='company_name',
            orientation='h',
            title="Top 15 Companies by Unique Licenses",
            labels={'company_name': 'Company Name', 'Unique Licenses': 'Number of Unique Licenses'},
            text='Unique Licenses'
        )
        fig_company_bar.update_layout(yaxis={'categoryorder':'total ascending'}, margin=dict(l=0, r=0, t=30, b=0))
        fig_company_bar.update_traces(textposition='outside')
        st.plotly_chart(fig_company_bar, use_container_width=True)
    else:
        st.info("No data to display top companies for the current filters.")


st.markdown("---")


# --- Row 3: Deeper Dive / Crosstabs ---
col5, col6 = st.columns([3, 2]) # Give stacked bar more space

with col5:
    st.subheader("📊 Country Distribution within Top Product Groups")
    if not df_filtered.empty:
        # Decide which groups and countries to show for clarity
        top_groups = df_filtered['group_name'].value_counts().nlargest(10).index
        top_countries = df_filtered['company_country'].value_counts().nlargest(10).index

        # Filter data for the stacked bar chart
        df_stacked_bar = df_filtered[
            df_filtered['group_name'].isin(top_groups) &
            df_filtered['company_country'].isin(top_countries)
        ]

        if not df_stacked_bar.empty:
             # Aggregate unique licenses for the combinations
             licenses_by_group_country = df_stacked_bar.groupby(['group_name', 'company_country'], observed=True)['licence_number'].nunique().reset_index()
             licenses_by_group_country.rename(columns={'licence_number': 'Unique Licenses'}, inplace=True)

             # Create Plotly Stacked Bar chart
             fig_stacked_bar = px.histogram(
                 licenses_by_group_country,
                 y='group_name',
                 x='Unique Licenses',
                 color='company_country',
                 title='Company Country Distribution in Top 10 Product Groups (Top 10 Countries)',
                 labels={'group_name': 'Product/Service Group', 'Unique Licenses': 'Number of Unique Licenses'},
                 category_orders={"group_name": top_groups.tolist()}, # Order groups by frequency
                 barmode='stack',
                 # height=600 # Adjust height if needed
             )
             fig_stacked_bar.update_layout(yaxis={'categoryorder':'total descending'}, margin=dict(l=0, r=10, t=30, b=0)) # Order groups
             st.plotly_chart(fig_stacked_bar, use_container_width=True)
        else:
             st.info("Not enough data overlap between top groups and top countries for the current filters.")
    else:
        st.info("No data to display group/country distribution for the current filters.")


with col6:
    st.subheader("⚖️ Product vs. Service Split")
    if not df_filtered.empty:
         # Aggregate unique licenses per product/service type
        prod_service_split = df_filtered.groupby('product_or_service', observed=True)['licence_number'].nunique().reset_index()
        prod_service_split.rename(columns={'licence_number': 'Unique Licenses'}, inplace=True)

        # Create Plotly Pie chart
        fig_pie = px.pie(
            prod_service_split,
            names='product_or_service',
            values='Unique Licenses',
            title='Product vs. Service Split (Unique Licenses)',
            hole=0.3 # Make it a donut chart
        )
        fig_pie.update_traces(textinfo='percent+label', pull=[0.05, 0.05]) # Add labels and pull slices slightly
        fig_pie.update_layout(margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No data to display product/service split for the current filters.")


# --- Optional: Display Filtered Data Table ---
st.markdown("---")
st.subheader("Filtered Data Sample")
if not df_filtered.empty:
    # Show a sample, select relevant columns maybe
    st.dataframe(df_filtered[['licence_number', 'product_or_service_name', 'group_name', 'company_name', 'company_country', 'expiration_date']].head(100))
else:
    st.info("No data available for the selected filters.")


# --- Footer / Data Source Info ---
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **Data Source:** [EU Open Data Portal - EU Ecolabel Products](https://data.europa.eu/data/datasets/eu-ecolabel-products?locale=en)
    **License:** Creative Commons Attribution 4.0 International
    **Note:** This dashboard aggregates data based on unique license numbers where appropriate.
    """
)