import pandas as pd
import numpy as np
import streamlit as st
import statsmodels.api as sm
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.graphics.gofplots import qqplot
from statsmodels.stats.outliers_influence import variance_inflation_factor

# Initialize session state for model storage
if 'trained_model' not in st.session_state:
    st.session_state.trained_model = None

def get_training_threshold(season_df):
    """Calculate training threshold: min(360 minutes, 60% of max minutes)"""
    if season_df.empty:
        return 0
    
    max_minutes = season_df['Minutes'].max()
    threshold_60pct = max_minutes * 0.6
    threshold = min(360, threshold_60pct)
    
    return threshold

st.title('Goal Involvement Prediction Model')
tab1, tab2 = st.tabs(["Player Predictions", "Model Training & Diagnostics"])

with tab2:
    st.header("Model Training & Analysis")
    
    # Load season data
    season_df = pd.read_csv("data/season_stats.csv").drop_duplicates(subset=['Player'], keep='first')
    
    # Calculate training threshold
    training_threshold = get_training_threshold(season_df)
    st.info(f"Training threshold: {training_threshold:.0f} minutes (minimum of 360 minutes or 60% of max season minutes)")
    
    # Filter players for training
    training_players = season_df[season_df['Minutes'] >= training_threshold].copy()
    st.write(f"Training on {len(training_players)} players out of {len(season_df)} total players")
    
    if len(training_players) >= 5:
        # Model preprocessing (no capping)
        training_players['xGChain_xGBuildup'] = training_players['xGChain90'] - training_players['xGBuildup90']
        training_players['SP_Chain_Buildup'] = (training_players['NPxG90_xA90'] - training_players['xGChain_xGBuildup']) / training_players['NPxG90_xA90']
        training_players.replace([np.inf, -np.inf], np.nan, inplace=True)
        training_players.dropna(inplace=True)

        # Unweighted OLS model setup
        y = training_players['NpGI90']
        X = sm.add_constant(training_players[['xGChain_xGBuildup', 'SP_Chain_Buildup', 'xA90']])
        model = sm.OLS(y, X).fit()
        
        # Store model in session state
        st.session_state.trained_model = model
        
        # Model Summary
        st.subheader("Model Summary")
        st.text(str(model.summary()))
        
        # Enhanced Model Diagnostics
        st.subheader("Model Diagnostics")
        
        # Top Metrics Row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("R-squared", f"{model.rsquared:.1%}", 
                     help="Proportion of variance explained by model")
        with col2:
            st.metric("Adj. R-squared", f"{model.rsquared_adj:.1%}",
                     help="R-squared adjusted for number of predictors")
        with col3:
            st.metric("F-statistic", f"{model.fvalue:.1f}",
                     help="Overall significance of model")
        with col4:
            st.metric("AIC/BIC", f"{model.aic:.1f}/{model.bic:.1f}",
                     help="Information criteria for model comparison")

        # Training Data Summary
        st.subheader("Training Data Summary")
        training_summary = training_players[['Minutes', 'NpGI90', 'xA90', 'NPxG90_xA90', 'xGChain90', 'xGBuildup90']].describe()
        st.dataframe(training_summary)

        # Assumption Checking Expandable Section
        with st.expander("Regression Assumption Checks", expanded=False):
            assumption_col1, assumption_col2, assumption_col3 = st.columns(3)
            
            # Normality Test
            _, p_norm = sm.stats.diagnostic.normal_ad(model.resid)
            assumption_col1.metric("Normality (p-value)", 
                                  f"{p_norm:.4f}",
                                  help="Anderson-Darling test of residual normality")
            
            # Heteroscedasticity Test
            _, p_het, _, _ = sm.stats.diagnostic.het_breuschpagan(model.resid, model.model.exog)
            assumption_col2.metric("Homoscedasticity (p-value)", 
                                  f"{p_het:.4f}",
                                  help="Breusch-Pagan test for constant variance")
            
            # Multicollinearity Check
            vif_data = pd.DataFrame()
            vif_data["Variable"] = X.columns
            vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
            max_vif = vif_data["VIF"].max()
            assumption_col3.metric("Max VIF", 
                                  f"{max_vif:.1f}",
                                  help="Variance Inflation Factor (VIF > 10 indicates multicollinearity)")
            
            # Display VIF table
            st.write("**Variance Inflation Factors:**")
            st.dataframe(vif_data.set_index("Variable"), use_container_width=True)
    else:
        st.error("Not enough players meet the training threshold for model fitting.")
        st.session_state.trained_model = None
with tab1:
    st.header('Player Ranking Based on Predicted Goal Involvements')
    
    # Check if model is trained
    if st.session_state.trained_model is None:
        st.warning("Please train the model first by visiting the 'Model Training & Diagnostics' tab.")
    else:
        model = st.session_state.trained_model
        
        # Load form data
        form_df = pd.read_csv("data/form_stats.csv").drop_duplicates(subset=['Player'], keep='first')
        
        if not form_df.empty:
            # Prepare form data for prediction (no capping)
            form_processed = form_df.copy()
            form_processed['xGChain_xGBuildup'] = form_processed['xGChain90'] - form_processed['xGBuildup90']
            form_processed['SP_Chain_Buildup'] = (form_processed['NPxG90_xA90'] - form_processed['xGChain_xGBuildup']) / form_processed['NPxG90_xA90']
            form_processed.replace([np.inf, -np.inf], np.nan, inplace=True)
            form_processed.dropna(inplace=True)
            
            # Get minutes - now both datasets should have Minutes column
            form_with_minutes = form_processed.copy()
            minutes_source = "last 5 games"
            
            # Make predictions using the trained model
            X_form = sm.add_constant(form_processed[['xGChain_xGBuildup', 'SP_Chain_Buildup', 'xA90']])
            form_with_minutes['Predicted_NpGI90'] = model.predict(X_form)
            
            # Add ranking
            form_with_minutes['Rank'] = form_with_minutes['Predicted_NpGI90'].rank(ascending=False, method='min')
            
            # Add low minutes flag
            form_with_minutes['Low_Minutes'] = form_with_minutes['Minutes'] < 180
            
            # Sort by rank
            df_ranked = form_with_minutes.sort_values(by='Rank')
            
            # Search functionality
            search_term = st.text_input("Search Player:")
            filtered_df = df_ranked.copy()
            if search_term:
                filtered_df = filtered_df[filtered_df['Player'].str.contains(search_term, case=False, na=False)]
            
            # Prepare display data
            display_df = filtered_df[[
                'Rank', 'Player', 'Team', 'Predicted_NpGI90', 'Minutes', 
                'xA90', 'NPxG90_xA90', 'xGChain90', 'xGBuildup90', 'Low_Minutes'
            ]].copy()
            
            # Round predictions for better display
            display_df['Predicted_NpGI90'] = display_df['Predicted_NpGI90'].round(3)
            
            # Display with conditional formatting
            st.subheader(f"Player Rankings ({len(display_df)} players)")
            
            # Prepare display data with color coding
            display_for_show = display_df.drop('Low_Minutes', axis=1).copy()
            
            # Simple approach: Add a visual indicator instead of complex styling
            display_for_show['Minutes_Status'] = display_df['Minutes'].apply(
                lambda x: f"⚠️ {x}" if x < 180 else str(x)
            )
            display_for_show = display_for_show.drop('Minutes', axis=1)
            
            # Reorder columns
            cols = ['Rank', 'Player', 'Team', 'Predicted_NpGI90', 'Minutes_Status', 
                    'xA90', 'NPxG90_xA90', 'xGChain90', 'xGBuildup90']
            display_for_show = display_for_show[cols]
            
            st.dataframe(display_for_show, height=600, use_container_width=True)
            
            # Legend and info
            st.markdown(f"""
            **Legend**: 
            - ⚠️ **Warning symbol**: Players with <180 minutes ({minutes_source})
            - **Predicted_NpGI90**: Predicted non-penalty goal involvements per 90 minutes based on last 5 games
            - **Rankings**: Based on recent form (last 5 games) applied to season-trained model
            - **Minutes_Status**: Minutes played ({minutes_source}) - ⚠️ indicates <180 minutes
            """)
            
            # Summary statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Players", len(df_ranked))
            with col2:
                low_min_count = (df_ranked['Minutes'] < 180).sum()
                st.metric(f"Low Minutes Players (<180 {minutes_source})", low_min_count)
            with col3:
                avg_prediction = df_ranked['Predicted_NpGI90'].mean()
                st.metric("Avg Predicted NpGI90", f"{avg_prediction:.3f}")
                
        else:
            st.error("No form data available. Please check data/form_stats.csv")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.write("© Fpl-Assistant All rights reserved.")

linkedin = "https://raw.githubusercontent.com/sahirmaharaj/exifa/main/img/linkedin.gif"
x1 = "https://unbounce.com/photos/metaX.svg"
email = "https://raw.githubusercontent.com/sahirmaharaj/exifa/main/img/email.gif"

with col3:
    st.caption(
    f"""
        <div style='display: flex; align-items: center;'>
            <a href = 'https://www.linkedin.com/in/kevin-ofori-900119235/'><img src='{linkedin}' style='width: 35px; height: 35px; margin-right: 25px;'></a>
            <a href = 'https://x.com/oforii_k'><img src='{x1}' style='width: 32px; height: 32px; margin-right: 25px;'></a>
            <a href = 'mailto:kevinagyei2017@gmail.com'><img src='{email}' style='width: 28px; height: 28px; margin-right: 25px;'></a>
        </div>
        """,
    unsafe_allow_html=True,
)