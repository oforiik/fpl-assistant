import pandas as pd
import numpy as np
import streamlit as st
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.graphics.gofplots import qqplot

st.title('Goal Involvement OLS Model')
tab1, tab2 = st.tabs(["NpGI90 Predictor", "Model Summary"])

with tab2:
    # Load the table using a SQL query
    df = pd.read_csv("data/season_stats.csv")  # Ensure the `data` directory exists or adjust the path()
    # Use `engine` for the connection
    df = df.drop_duplicates(subset=['Player'], keep='first')
    threshold = df['Minutes'].max() * 0.6
    df = df[df['Minutes'] >= threshold]

    # Data preprocessing
    df['xGChain_xGBuildup'] = df['xGChain90'] - df['xGBuildup90']
    df['SP_Chain_Buildup'] = (df['NPxG90_xA90'] - df['xGChain_xGBuildup']) / df['NPxG90_xA90']
    df['SP_Chain_Buildup_sq'] = df['SP_Chain_Buildup'] ** 2

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()

    # Dependent variable (Y)
    y = df['NpGI90']

    # Independent variables (X)
    X = df[['xGChain_xGBuildup', 'SP_Chain_Buildup', 'xA90']]

    # Add constant to the independent variables
    X = sm.add_constant(X)

    # Fit the model
    model = sm.OLS(y, X).fit()
    xGChain_xGBuildup_coef = model.params['xGChain_xGBuildup']  
    sp_chain_coef = model.params['SP_Chain_Buildup']  
    xA90_coef = model.params['xA90']
    r_squared = model.rsquared
    
    # Explanation section
    st.subheader("Variable Definitions")
    st.markdown(f"""
    - **SP_Chain_Buildup**: This variable is highly significant, with a coefficient of {sp_chain_coef:.4f}. This means that for every 10% increase in the share of a player’s npxGI that comes from being involved in the earlier possesion sequence(buildup) or set pieces, npGI per 90 increases by {sp_chain_coef/10:.2f}.
    - **xA90**: Expected assists per 90 minutes, significant with a coefficient of {xA90_coef:.4f}. This means that for every 1 unit increase in xA90, npGI90 increases by approximately {xA90_coef:.2f} 
    - **xGChain_xGBuildup**: This variable is highly significant, with a coefficient of {xGChain_xGBuildup_coef:.4f}. This means that for every 1 unit increase in npxG derived from a player's direct involvement in the final action (either the last pass or the shot), npGI per 90 increases by approximately {xGChain_xGBuildup_coef:.2f}.
    - **R-squared**: Represents the percentage of NpGI90 explained by the model. Currently, just over {r_squared * 100:.2f}% of the variance of npGI90 is explained by the model.
    """)
    
    st.divider()
    st.subheader('OLS Model Summary')
    
    st.write(model.summary())

    st.divider()

    # Plotting section
    st.header('OLS Model Graphs')
    col1, col2, col3 = st.columns(3)
    # Fitted vs Actual Plot
    fitted_values = model.fittedvalues
    residuals = model.resid

    plt.figure(figsize=(10, 6))
    sns.scatterplot(x=fitted_values, y=y)
    plt.xlabel('Fitted Values (Predicted NpGI90)')
    plt.ylabel('Actual Values (NpGI90)')
    with col1:
        plt.title('Fitted vs Actual Values')
        with st.expander('Fitted vs Actual Values'):
            st.pyplot(plt)

    # Residual Plot
    plt.figure(figsize=(10, 6))
    sns.scatterplot(x=fitted_values, y=residuals)
    plt.axhline(0, color='red', linestyle='--')
    plt.xlabel('Fitted Values (Predicted NpGI90)')
    plt.ylabel('Residuals')
    with col2:
        plt.title('Residual Plot')
        with st.expander('Residual Plot'):
            st.pyplot(plt)

    # QQ Plot
    plt.figure(figsize=(10, 6))
    qqplot(residuals, line='s')
    with col3:
        plt.title('QQ Plot of Residuals')
        with st.expander('QQ Plot of Residuals'):
            st.pyplot(plt)

# st.divider()
with tab1:
    # Input fields for user to enter new explanatory variables
    st.header('Goal Involvement Calculator')
    xgchain = st.number_input('Enter xGChain90:', min_value=0.0, step=0.01)
    xgbuildup = st.number_input('Enter xGBuildup90:', min_value=0.0, step=0.01)
    npxG90 = st.number_input('Enter npxG90:', min_value=0.0, step=0.01)
    xA90 = st.number_input('Enter xA90:', min_value=0.0, step=0.01)
    npxG90_xA90 = npxG90 + xA90
    Sp_Chain = 0
    if npxG90_xA90 != 0:
        Sp_Chain = (npxG90_xA90 - xgchain + xgbuildup) / npxG90_xA90

    # Create a DataFrame for the input
    input_data = pd.DataFrame({
        'const': [1],  # Adding constant for the intercept
        'xGChain_xGBuildup': [xgchain - xgbuildup],
        'SP_Chain_Buildup': [Sp_Chain],
        'xA90': [xA90]
    })

    # When the user inputs values, use the model to predict NpGI90
    if st.button('Predict NpGI90'):
        predicted_npgi = model.predict(input_data)[0]  # Use the regression model for prediction
        st.success(f'The predicted NpGI90 is: {predicted_npgi:.2f}')

    st.divider()
    st.subheader('Player Ranking Based on Predicted Goal Involvements')
    df = pd.read_csv("data/form_stats.csv")  # Ensure the `data` directory exists or adjust the path
    df = df.drop_duplicates(subset=['Player'], keep='first')

    # Data processing for ranking
    df['npxG90'] = df['NPxG90_xA90'] - df['xA90']
    df['xGChain_xGBuildup'] = df['xGChain90'] - df['xGBuildup90']
    df['SP_Chain_Buildup'] = (df['NPxG90_xA90'] - df['xGChain_xGBuildup']) / df['NPxG90_xA90']

    df = df.replace([np.inf, -np.inf], np.nan)
    df = df.dropna()

    # Prepare independent variables (X) for OLS model
    X = df[['xGChain_xGBuildup', 'SP_Chain_Buildup', 'xA90']]

    # Add constant term for the OLS model
    X = sm.add_constant(X)

    # Dependent variable (Y) is NpGI90
    y = df['NPxG90_xA90']  # NpGI90 can be predicted using xGChain, xGBuildup, xA

    # Fit the OLS model
    model = sm.OLS(y, X).fit()

    # Use the model to predict NpGI90 for each player
    df['NPGI Per 90'] = model.predict(X)

    # Rank players based on predicted NpGI90
    df['Rank'] = df['NPGI Per 90'].rank(ascending=False)

    # Sort the players by rank
    df_ranked = df.sort_values(by='Rank')

    # Show only selected columns in a scrollable table
    columns_to_display = ['Rank', 'Player', 'Team', 'NPGI Per 90', 'npxG90', 'xA90', 'xGChain90', 'xGBuildup90']
    st.dataframe(df_ranked[columns_to_display], height=600)  # Set a fixed height for scrollability


# Adding contact information as a footer
st.markdown("---")  # Line separator
st.markdown(
    """
    **Contact Information**  
    📧 Email: [kevinagyei2017@gmail.com](mailto:kevinagyei2017@gmail.com)  
    🐦 Twitter: [@oforii_k](https://x.com/oforii_k)  
    """,
    unsafe_allow_html=True
)