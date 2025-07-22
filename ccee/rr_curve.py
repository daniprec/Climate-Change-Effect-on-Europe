from typing import Dict, Tuple

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
    lag_knots: list = None,
    verbose: bool = True,
) -> Tuple[GLMResults, pd.DataFrame, Dict]:
    """
    Fit a weekly Distributed Lag Non-linear Model (DLNM) with a
    temperature-lag cross-basis built from B-spline bases and estimate the
    association through a Poisson GLM.

    Parameters
    ----------
    df : pandas.DataFrame
        Tidy data frame whose index is a DatetimeIndex (weekly frequency)
        and that contains the exposure column x_col and the outcome column
        y_col. Any rows with missing values in these two columns are dropped
        automatically.
    x_col : str
        Name of the continuous exposure variable (e.g. mean weekly temperature).
    y_col : str
        Name of the count outcome variable (e.g. weekly mortality counts).
    max_lag : int, default 3
        Maximum number of weeks to lag x_col when constructing the
        cross-basis.
    knots_percentiles : list of int, default [10, 75, 90]
        Percentiles used to position internal knots for the temperature
        spline. Passed verbatim to :func:numpy.percentile.
    lag_knots : list or None, default None
        Explicit positions (in weeks) of internal knots for the lag spline.
        If None, they are set to equally spaced locations between 0 and
        max_lag (exclusive of the boundaries).
    verbose : bool, default True
        Whether to print the model summary returned by statsmodels.GLM.

    Returns
    -------
    model : statsmodels.genmod.generalized_linear_model.GLMResults
        Fitted log-linear (Poisson) GLM.
    crossbasis_df : pandas.DataFrame
        The full cross-basis design matrix supplied to the GLM; has
        n_temp x n_lag columns labelled cb_i_j.
    crossbasis_spec : dict
        Metadata needed for post-estimation tasks (knots, formulas, degrees,
        etc.).

    Notes
    -----
    * The cross-basis W is constructed as the Kronecker product of the
      temperature basis B(x_t) and the lag basis C(ell) and follows the
      definition in Equation (7) of Gasparrini (2010).
    * Fixed effects for calendar week and year are added to control for
      seasonality and long-term trends; customise this block if you need a
      finer temporal adjustment.
    * Over-dispersion is not handled here (plain Poisson). Switch to
      quasi-Poisson by adding scale="X2" in the GLM call when required.

    References
    ----------
    Gasparrini, A. (2010). Distributed lag non-linear models. Statistics in
    Medicine, 29(21), 2224-2234. https://doi.org/10.1002/sim.3940
    """
    df = df[[x_col, y_col]].copy().dropna()

    # Temperature spline basis specification
    temp_knots = np.percentile(df[x_col], knots_percentiles)
    temp_formula = f"bs(x, knots={list(temp_knots)}, degree=2, include_intercept=False)"
    Z = dmatrix(temp_formula, {"x": df[x_col]}, return_type="dataframe")
    Z.reset_index(drop=True, inplace=True)
    n_temp = Z.shape[1]

    # Lag spline basis (time-invariant)
    if lag_knots is None:
        lag_knots = np.linspace(0, max_lag, min(4, max_lag + 1))[1:-1]
    lag_formula = f"bs(lag, knots={list(lag_knots)}, degree=2, include_intercept=False)"
    C = dmatrix(lag_formula, {"lag": np.arange(max_lag + 1)}, return_type="dataframe")
    C.index = np.arange(max_lag + 1)  # for easy lookup
    n_lag = C.shape[1]

    # Build cross-basis for every observation
    #     cb_{i}_{j}  where i = temp basis, j = lag basis
    cross_cols = [f"cb_{i}_{j}" for j in range(n_lag) for i in range(n_temp)]
    crossbasis_df = pd.DataFrame(0.0, index=df.index, columns=cross_cols)

    for ell in range(max_lag + 1):
        # temperature values at lag ell
        x_lag = df[x_col].shift(ell)
        # rows that became NaN because of the shift should be skipped
        valid = x_lag.notna()
        if not valid.any():
            continue

        temp_basis_lag = dmatrix(
            temp_formula, {"x": x_lag[valid]}, return_type="dataframe"
        ).to_numpy()  # (n_valid, n_temp)
        w = C.loc[ell].to_numpy()  # (n_lag,)

        # Add contributions: Z_lag (n_valid x n_temp) ⊗ w (n_lag,)
        kron_block = np.kron(w, temp_basis_lag)  # (n_valid, n_temp*n_lag)
        crossbasis_df.loc[valid, cross_cols] += kron_block

    # drop rows with any remaining NaNs (due to initial lags)
    mask_complete = crossbasis_df.notna().all(axis=1)
    df = df.loc[mask_complete].copy()
    crossbasis_df = crossbasis_df.loc[mask_complete]

    # Time dummy adjustment (week * year)
    df["week"] = df.index.isocalendar().week.astype(str)
    df["year"] = df.index.year.astype(str)
    time_dummies = pd.get_dummies(df[["week", "year"]], drop_first=True).astype(float)

    X = pd.concat(
        [pd.Series(1.0, index=df.index, name="intercept"), crossbasis_df, time_dummies],
        axis=1,
    ).astype(float)
    y = df[y_col].astype(float)

    model = sm.GLM(y, X, family=sm.families.Poisson()).fit()
    if verbose:
        print(model.summary())

    spec = {
        "temp_formula": temp_formula,
        "lag_formula": lag_formula,
        "temp_knots": temp_knots.tolist(),
        "lag_knots": list(lag_knots),
        "temp_degree": 2,
        "lag_degree": 2,
        "n_temp": n_temp,
        "n_lag": n_lag,
        "max_lag": max_lag,
        "x_col": x_col,
        "y_col": y_col,
    }
    return model, crossbasis_df, spec


def plot_rr_curve(
    model: GLMResults,
    spline_spec: dict,
    xrange: tuple,
    max_lag: int,
    ref_temp: float = None,
    n_grid: int = 100,
):
    """
    Plot the overall (lag-integrated) temperature-risk curve derived from a
    fitted DLNM.

    The function constructs the marginal cross-basis row
    ∑_ell C(ell) cx B(x) (i.e. integrates over lags) and combines it with the
    coefficient vector and its covariance to obtain point estimates and
    95 % confidence bands for the Relative Risk (RR) across a temperature grid.

    Parameters
    ----------
    model : statsmodels.genmod.generalized_linear_model.GLMResults
        GLM returned by fit_dlnm_weekly.
    spline_spec : dict
        Output crossbasis_spec from fit_dlnm_weekly.
    xrange : tuple
        Lower and upper bounds of the temperature grid in the same units as
        x_col.
    max_lag : int
        Maximum lag (must match the value used at fitting time).
    ref_temp : float or None, default None
        Temperature at which RR = 1.  If None, the temperature with
        minimum estimated RR on the grid is used.
    n_grid : int, default 100
        Number of equally spaced temperature points for the plot.

    Returns
    -------
    None
        The function creates a Matplotlib figure and shows it.

    Notes
    -----
    * Confidence intervals are computed via the delta method using the full
      coefficient covariance matrix model.cov_params.  If a quasi-Poisson
      model was fitted, remember to inflate the standard errors by
      √model.scale before plotting.
    * This is conceptually identical to the crosspred(..., type="overall")
      method in the dlnm R package (Gasparrini 2010).

    References
    ----------
    Gasparrini, A. (2010). Distributed lag non-linear models. Statistics in
    Medicine, 29(21), 2224-2234. https://doi.org/10.1002/sim.3940
    """
    # build temperature grid & basis
    temps = np.linspace(*xrange, n_grid)
    Zg = dmatrix(spline_spec["temp_formula"], {"x": temps}, return_type="dataframe")
    n_temp = Zg.shape[1]

    # lag-basis rows & their sum (∑_lag c_k(ℓ))
    C = dmatrix(
        spline_spec["lag_formula"],
        {"lag": np.arange(max_lag + 1)},
        return_type="dataframe",
    )
    lag_sum = C.sum(axis=0).to_numpy()  # (n_lag,)
    n_lag = lag_sum.size

    # coefficient vector & covariance
    cross_names = [f"cb_{i}_{j}" for j in range(n_lag) for i in range(n_temp)]
    beta = model.params[cross_names].to_numpy()
    V = model.cov_params().loc[cross_names, cross_names].to_numpy()

    # helper to build cross-basis row = kron(lag_sum, Z_row)
    def cross_row(z_row: np.ndarray) -> np.ndarray:
        return np.kron(lag_sum, z_row)  # length n_temp * n_lag

    # compute log-RR & SE for the grid
    log_rr, se = [], []
    for z in Zg.to_numpy():
        s = cross_row(z)
        log_rr.append(s @ beta)
        se.append(np.sqrt(s @ V @ s))
    log_rr = np.array(log_rr)
    se = np.array(se)

    # reference temperature
    if ref_temp is None:
        idx_ref = np.argmin(np.exp(log_rr))
        ref_temp = temps[idx_ref]
        ref_log_rr = log_rr[idx_ref]
    else:
        z_ref = dmatrix(
            spline_spec["temp_formula"], {"x": [ref_temp]}, return_type="dataframe"
        ).to_numpy()[0]
        ref_log_rr = cross_row(z_ref) @ beta

    # normalise & exponentiate
    log_rr -= ref_log_rr
    rr = np.exp(log_rr)
    rr_low = np.exp(log_rr - 1.96 * se)
    rr_high = np.exp(log_rr + 1.96 * se)

    # plot
    plt.figure(figsize=(7, 4))
    plt.plot(temps, rr, color="darkred", lw=2, label="Marginal RR")
    plt.fill_between(
        temps, rr_low, rr_high, color="darkred", alpha=0.25, label="95% CI"
    )
    plt.axhline(1.0, ls="--", color="gray")
    plt.xlabel("Temperature (°C)")
    plt.ylabel("Relative Risk (RR)")
    plt.title(f"Marginal RR vs Temperature (ref = {ref_temp:.1f}°C)")
    plt.grid(True, ls=":", lw=0.5)
    plt.legend()
    plt.tight_layout()
    plt.show()
