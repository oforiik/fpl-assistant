import pandas as pd
import numpy as np
import streamlit as st
import statsmodels.api as sm
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.graphics.gofplots import qqplot
from statsmodels.stats.outliers_influence import variance_inflation_factor
# Initialize session state for persistent storage
if 'season_caps' not in st.session_state:
    st.session_state.season_caps = {}

def calculate_season_caps(season_df, threshold_pct):
    """Calculate capping thresholds from season data using dynamic threshold"""
    if season_df.empty or threshold_pct <= 0:
        return {}
    
    max_minutes = season_df['Minutes'].max()
    threshold = max_minutes * threshold_pct
    
    eligible = season_df[season_df['Minutes'] >= threshold]
    if len(eligible) < 5:
        st.warning(f"Not enough qualified players ({len(eligible)}) at {threshold_pct:.0%} threshold!")
        return {}
    
    return {
        'xA90': eligible['xA90'].quantile(0.95),
        'NPxG90_xA90': eligible['NPxG90_xA90'].quantile(0.95),
        'xGChain90': eligible['xGChain90'].quantile(0.95),
        'xGBuildup90': eligible['xGBuildup90'].quantile(0.95)
    }

def apply_capping(df, caps):
    """Apply capping to dataframe using pre-calculated caps"""
    if not caps or df.empty:
        return df
    
    capped_df = df.copy()
    for col, cap in caps.items():
        if col in capped_df.columns:
            capped_df[col] = np.minimum(capped_df[col], cap)
    return capped_df

st.title('Goal Involvement OLS Model')
tab1, tab2 = st.tabs(["NpGI90 Predictor", "Model Summary"])

with tab2:
    # Load season data
    season_df = pd.read_csv("data/season_stats.csv").drop_duplicates(subset=['Player'], keep='first')
    
    # Dynamic threshold control
    threshold_pct = st.slider(
        'Season minutes threshold (%)', 
        0, 100, 60,
        format='%d%%',
        help="Percentage of maximum season minutes required for uncapped stats"
    ) / 100
    
    # Calculate and store capping thresholds
    st.session_state.season_caps = calculate_season_caps(season_df, threshold_pct)
    
    if st.session_state.season_caps:
        # Apply capping to season data
        capped_season = apply_capping(season_df, st.session_state.season_caps)
        
        # Model preprocessing
        capped_season['xGChain_xGBuildup'] = capped_season['xGChain90'] - capped_season['xGBuildup90']
        capped_season['SP_Chain_Buildup'] = (capped_season['NPxG90_xA90'] - capped_season['xGChain_xGBuildup']) / capped_season['NPxG90_xA90']
        capped_season.replace([np.inf, -np.inf], np.nan, inplace=True)
        capped_season.dropna(inplace=True)

        # Weighted model setup
        y = capped_season['NpGI90']
        X = sm.add_constant(capped_season[['xGChain_xGBuildup', 'SP_Chain_Buildup', 'xA90']])
        model = sm.WLS(y, X, weights=capped_season['Minutes']).fit()
        
        # New Enhanced Model Diagnostics Section
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

        # Assumption Checking Expandable Section
        with st.expander("Regression Assumption Checks", expanded=True):
            assumption_col1, assumption_col2, assumption_col3 = st.columns(3)
            
            # Normality Test
            _, p_norm = sm.stats.diagnostic.normal_ad(model.resid)
            assumption_col1.metric("Normality (p-value)", 
                                  f"{p_norm:.4f}",
                                  help="Jarque-Bera test of residual normality")
            
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
        # Enhanced Variable Analysis Section
        with st.expander("Detailed Variable Analysis", expanded=True):
            # Coefficient Plot
            plt.figure(figsize=(10, 4))
            model.params[1:].plot(kind='barh')  # Exclude intercept
            plt.title("Standardized Coefficient Magnitudes")
            plt.xlabel("Effect Size")
            st.pyplot(plt)
            
            # Partial Regression Plots
            st.write("**Partial Regression Plots**")
            fig = plt.figure(figsize=(15, 5))
            sm.graphics.plot_partregress_grid(model, fig=fig)
            st.pyplot(fig)

        # Model Comparison Section
        with st.expander("Model Comparison", expanded=False):
            # Compare with unweighted model
            simple_model = sm.OLS(y, X).fit()
            comparison_df = pd.DataFrame({
                'Weighted': [model.rsquared, model.aic, model.bic],
                'Unweighted': [simple_model.rsquared, simple_model.aic, simple_model.bic]
            }, index=['R-squared', 'AIC', 'BIC'])
            st.dataframe(comparison_df.style.format("{:.2f}"), 
                        use_container_width=True)

        # Interactive Coefficient Explorer
        with st.expander("Interactive Coefficient Exploration"):
            selected_var = st.selectbox("Choose variable to explore:", 
                                       model.params.index[1:])  # Exclude intercept
            var_details = {
                'Coefficient': model.params[selected_var],
                'P-value': model.pvalues[selected_var],
                'CI Lower': model.conf_int().loc[selected_var, 0],
                'CI Upper': model.conf_int().loc[selected_var, 1]
            }
            st.json(var_details)
            
            # Individual residual plot
            plt.figure(figsize=(10, 4))
            sns.regplot(x=X[selected_var], y=model.resid, lowess=True)
            plt.axhline(0, color='red', linestyle='--')
            plt.title(f"Residuals vs {selected_var}")
            st.pyplot(plt)

        # Replace original plots with more informative versions
        with st.expander("Advanced Diagnostics", expanded=False):
            # Calculate leverage and Cook's distance manually
            try:
                # For OLS models
                influence = model.get_influence()
            except AttributeError:
                # For WLS models
                X = model.model.exog
                w = model.model.weights  # Get weights from WLS model
                w_sqrt = np.sqrt(w)
                X_weighted = w_sqrt[:, None] * X
                hat_matrix_diag = np.diag(X_weighted @ np.linalg.pinv(X_weighted.T @ X_weighted) @ X_weighted.T)
                cooks = (model.resid**2 / (X.shape[1] * model.mse_resid)) * (hat_matrix_diag / (1 - hat_matrix_diag)**2)
            else:
                # For OLS models
                hat_matrix_diag = influence.hat_matrix_diag
                cooks = influence.cooks_distance[0]

            # Cook's Distance Plot
            plt.figure(figsize=(10, 4))
            plt.stem(cooks, markerfmt=",")
            plt.title("Cook's Distance for Influential Points")
            plt.xlabel("Observation Index")
            plt.ylabel("Cook's Distance")
            st.pyplot(plt)
            
            # Leverage Plot
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.scatter(hat_matrix_diag, model.resid_pearson)
            ax.set_xlabel("Leverage (Hat values)")
            ax.set_ylabel("Standardized Residuals")
            ax.set_title("Leverage vs Residuals")
            st.pyplot(fig)
with tab1:
    # Load pre-filtered form data (already ≥180 mins)
    form_df = pd.read_csv("data/form_stats.csv").drop_duplicates(subset=['Player'], keep='first')
    
    # Apply season-based capping from session state
    capped_form = apply_capping(form_df, st.session_state.get('season_caps', {}))
    
    if not st.session_state.season_caps:
        st.warning("Season caps not calculated yet - using uncapped data. Adjust threshold in Model Summary tab first.")
    
    # Form model processing
    capped_form['npxG90'] = capped_form['NPxG90_xA90'] - capped_form['xA90']
    capped_form['xGChain_xGBuildup'] = capped_form['xGChain90'] - capped_form['xGBuildup90']
    capped_form['SP_Chain_Buildup'] = (capped_form['NPxG90_xA90'] - capped_form['xGChain_xGBuildup']) / capped_form['NPxG90_xA90']
    capped_form.replace([np.inf, -np.inf], np.nan, inplace=True)
    capped_form.dropna(inplace=True)

    # Prediction model
    X_form = sm.add_constant(capped_form[['xGChain_xGBuildup', 'SP_Chain_Buildup', 'xA90']])
    y_form = capped_form['NPxG90_xA90']
    form_model = sm.OLS(y_form, X_form).fit()
    
    # Generate predictions and rankings
    capped_form['NPGI Per 90'] = form_model.predict(X_form)
    capped_form['Rank'] = capped_form['NPGI Per 90'].rank(ascending=False)
    df_ranked = capped_form.sort_values(by='Rank')

    # Search implementation
    st.header('Player Ranking Based on Predicted Goal Involvements')
    search_term = st.text_input("Search Player:")
    
    # Filter based on search
    filtered_df = df_ranked.copy()
    if search_term:
        filtered_df = filtered_df[filtered_df['Player'].str.contains(search_term, case=False)]
    
    # Display results
    columns_to_display = ['Rank', 'Player', 'Team', 'NPGI Per 90', 'npxG90', 'xA90', 'xGChain90', 'xGBuildup90']
    st.dataframe(filtered_df[columns_to_display], height=600)
    
    st.markdown("""
    **Guide**: Rankings based on last 5 games (min 180 mins played). 
    Stats capped using season-long 95th percentile values from players meeting the threshold.
    """)

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