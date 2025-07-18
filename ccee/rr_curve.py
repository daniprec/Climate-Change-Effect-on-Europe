import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from patsy import dmatrix
from scipy.stats import percentileofscore
from statsmodels.genmod.generalized_linear_model import GLMResults


def compute_percentiles(
    df: pd.DataFrame, col: str, groupby: str = "NUTS_ID"
) -> pd.Series:
    """
    Compute percentiles of a column grouped by 'NUTS_ID'.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with the column to compute percentiles on.
    col : str
        Column name to compute percentiles for.
    groupby : str
        Column name to group by, default is 'NUTS_ID'.

    Returns
    -------
    pd.Series
        Percentile values for each row in the specified column.
    """
    return df.groupby(groupby)[col].transform(
        lambda x: percentileofscore(x, x, kind="rank") / 100.0
    )


def fit_dlnm_weekly(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    max_lag: int = 3,
    knots_percentiles: list = [10, 75, 90],
    verbose: bool = True,
) -> tuple[GLMResults, pd.DataFrame, dict]:
    """
    Fit a simplified Distributed Lag Non-Linear Model (DLNM) using weekly data
    and Poisson regression with natural cubic splines on time lags.

    Parameters
    ----------
    df : pd.DataFrame
        Must be indexed by datetime.
    x_col : str
        Name of x column.
    y_col : str
        Name of Y column.
    max_lag : int
        Max lag to include, in weeks, by default 3.
    knots_percentiles : list of float
        Percentiles for spline knots, by default [10, 75, 90].
    verbose : bool
        Print GLM summary if True.

    Returns
    -------
    model : statsmodels GLMResults
    splines_df : pd.DataFrame
        Combined lagged spline predictors used in the model.
    spline_spec : dict
        Dictionary with knot locations and spline formula per lag.
    """
    # Drop rows with NA values in key columns
    df = df[[x_col, y_col]].dropna().copy()

    if len(df) <= max_lag + 1:
        raise ValueError(f"Not enough rows after NaN removal for {max_lag} lags.")

    # Compute knots globally
    knot_vals = np.percentile(df[x_col].values, knots_percentiles)

    lagged_splines = []
    spline_spec = {}  # to save spline info per lag
    common_idx = None

    for lag in range(max_lag + 1):
        # Lag the x
        df_lagged = df.copy()
        df_lagged["lagged_x"] = df[x_col].shift(lag)
        df_lagged.dropna(inplace=True)

        # Build spline basis
        formula = (
            f"bs(lagged_x, knots={list(knot_vals)}, degree=2, include_intercept=False)"
        )
        design = dmatrix(formula, data=df_lagged, return_type="dataframe")
        design.columns = [f"spline_lag{lag}_{i}" for i in range(design.shape[1])]
        design.index = df_lagged.index

        # Store design and formula
        lagged_splines.append(design)
        spline_spec[lag] = {
            "formula": formula,
            "knots": knot_vals,
            "degree": 2,
        }

        # Track valid index
        if common_idx is None:
            common_idx = design.index
        else:
            common_idx = common_idx.intersection(design.index)

    # Final design matrix
    X_spline = pd.concat([d.loc[common_idx] for d in lagged_splines], axis=1)

    # Add time dummies (week and year) as fixed effects
    df_sub = df.loc[common_idx].copy()
    df_sub["week"] = df_sub.index.isocalendar().week.astype(str)
    df_sub["year"] = df_sub.index.year.astype(str)
    time_dummies = pd.get_dummies(df_sub[["week", "year"]], drop_first=True).astype(
        float
    )

    # Add intercept manually
    intercept = pd.Series(1.0, index=common_idx, name="intercept")

    # Build final matrix
    x = pd.concat([intercept, X_spline, time_dummies], axis=1).astype(float)
    y = df_sub[y_col].astype(float)

    # Fit Poisson GLM
    model = sm.GLM(y, x, family=sm.families.Poisson()).fit()

    if verbose:
        print(model.summary())

    return model, X_spline, spline_spec


def plot_rr_curve(model: GLMResults, spline_spec: dict, xrange: tuple, lag: int = 0):
    """
    Plot the relative risk (RR) curve for a specific lag.

    Parameters
    ----------
    model : statsmodels GLMResults
        Fitted Poisson GLM.
    spline_spec : dict
        Dictionary with spline formulas and knots per lag (from fit_dlnm_weekly).
    xrange : tuple of float
        x range to evaluate the RR curve over.
    lag : int
        Lag to evaluate the effect at (e.g., 0 for lag 0).
    """
    # Temperature grid
    x = np.linspace(xrange[0], xrange[1], 100)

    # Rebuild spline basis for this lag
    formula = spline_spec[lag]["formula"]
    basis = dmatrix(formula, {"lagged_x": x}, return_type="dataframe")
    basis.columns = [f"spline_lag{lag}_{i}" for i in range(basis.shape[1])]

    # Extract model coefficients for this lag
    coef = model.params[basis.columns]
    log_rr = basis.values @ coef.values
    rr = np.exp(log_rr)

    # Normalize RR to 1 at the minimum point (reference temperature)
    rr /= rr.min()

    # Plot
    plt.plot(x, rr, label=f"Lag {lag} weeks")
