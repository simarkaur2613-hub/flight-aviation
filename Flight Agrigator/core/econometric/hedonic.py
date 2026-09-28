"""
Hedonic Price Regression & Quality Adjustment Model.
Decomposes airline ticket prices into implicit shadow prices for flight characteristics
following the ONS, Eurostat, and IMF Hedonic CPI Framework.

Model Specification:
ln(Fare) = beta_0 + beta_1 * ln(Distance) + beta_2 * Is_Peak_Hour + beta_3 * (Lead_Days / 30) + beta_4 * Is_LCC + e

Where:
- Is_Peak_Hour: 1 if departing during morning peak (07:00-09:30) or evening peak (17:30-20:30)
- Is_LCC: 1 if Low-Cost Carrier (no complimentary meals/baggage), 0 if Full-Service Carrier
- Lead_Days: Normalised advance booking horizon
- ln(Distance): Natural log of stage length in kilometers
"""

import math
import numpy as np
import pandas as pd
from core.models import FlightQuote


def run_hedonic_regression():
    """
    Fits an Ordinary Least Squares (OLS) hedonic price regression on flight quote microdata.
    Estimates shadow prices for quality attributes and decomposes pure inflation from quality shifts.
    """
    quotes = FlightQuote.objects.filter(is_outlier=False).select_related('route', 'airline')
    if quotes.count() < 30:
        return {"status": "error", "message": "Insufficient data sample for regression."}

    data = []
    for q in quotes:
        # Peak departure hours: 7 to 10 am, or 17 to 20 pm
        try:
            hour = int(q.departure_time.split(':')[0])
        except (ValueError, IndexError):
            hour = 12
        is_peak = 1.0 if (7 <= hour <= 9 or 17 <= hour <= 20) else 0.0
        is_lcc = 1.0 if q.airline.is_lcc else 0.0
        dist = max(100.0, float(q.route.distance_km))

        data.append({
            "ln_fare": math.log(max(500.0, q.fare_inr)),
            "ln_dist": math.log(dist),
            "is_peak": is_peak,
            "lead_norm": float(q.lead_days) / 30.0,
            "is_lcc": is_lcc,
            "fare_inr": q.fare_inr,
            "lead_days": q.lead_days
        })

    df = pd.DataFrame(data)
    n = len(df)

    # Design matrix X: [Intercept, ln(dist), is_peak, lead_norm, is_lcc]
    X = np.column_stack([
        np.ones(n),
        df['ln_dist'].values,
        df['is_peak'].values,
        df['lead_norm'].values,
        df['is_lcc'].values
    ])
    y = df['ln_fare'].values

    # OLS estimation via least squares
    beta, residuals, rank, s = np.linalg.lstsq(X, y, rcond=None)

    # Calculate R-squared and statistics
    y_pred = X @ beta
    ss_total = np.sum((y - np.mean(y)) ** 2)
    ss_residual = np.sum((y - y_pred) ** 2)
    r_squared = 1.0 - (ss_residual / ss_total) if ss_total > 0 else 0.0

    # Degrees of freedom and variance
    df_e = n - X.shape[1]
    mse = ss_residual / df_e if df_e > 0 else 0.0
    var_beta = mse * np.linalg.inv(X.T @ X)
    se_beta = np.sqrt(np.diagonal(var_beta))

    # Variable labels and economic interpretation
    feature_names = [
        {"name": "Constant (Base Fare Intercept)", "desc": "Baseline fixed flight setup fee"},
        {"name": "Stage Length [ln(Distance)]", "desc": "Distance elasticity of fare"},
        {"name": "Peak Business Hours (Morning/Evening)", "desc": "Shadow price of peak departure convenience"},
        {"name": "Advance Horizon (Lead Time)", "desc": "Yield discount for early booking"},
        {"name": "Carrier Model (Low-Cost vs Full-Service)", "desc": "FSC premium (baggage, meals, lounge)"}
    ]

    regression_table = []
    for i in range(len(feature_names)):
        b_val = beta[i]
        se_val = se_beta[i]
        t_stat = b_val / se_val if se_val > 0 else 0.0
        # Percentage effect: [exp(beta) - 1] * 100 for dummy variables
        pct_effect = (math.exp(b_val) - 1.0) * 100.0 if i in [2, 4] else b_val * 100.0

        regression_table.append({
            "variable": feature_names[i]["name"],
            "description": feature_names[i]["desc"],
            "coefficient": round(float(b_val), 4),
            "std_error": round(float(se_val), 4),
            "t_statistic": round(float(t_stat), 2),
            "pct_impact": round(float(pct_effect), 1),
            "is_significant": abs(t_stat) > 1.96
        })

    # Quality-adjusted pure price index estimate
    # Controls for sample composition changes
    unadjusted_mean_fare = float(df['fare_inr'].mean())
    quality_adjusted_mean_fare = math.exp(beta[0] + beta[1] * math.log(1148.0) + beta[2] * 0.4 + beta[3] * 0.5 + beta[4] * 0.8)

    return {
        "status": "success",
        "sample_size": n,
        "r_squared": round(float(r_squared), 4),
        "f_statistic": round(float(((ss_total - ss_residual) / 4) / mse), 2) if mse > 0 else 0.0,
        "regression_table": regression_table,
        "unadjusted_mean_fare": round(unadjusted_mean_fare, 0),
        "quality_adjusted_mean_fare": round(quality_adjusted_mean_fare, 0),
        "quality_adjustment_gap_pct": round(((quality_adjusted_mean_fare / unadjusted_mean_fare) - 1.0) * 100.0, 2)
    }
