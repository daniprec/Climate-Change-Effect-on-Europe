from math import ceil, floor
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import typer
from patsy import dmatrix
from scipy.stats import percentileofscore
from statsmodels.genmod.generalized_linear_model import GLMResults

DICT_LABELS = {"temp_era5_q50": ("Temperature", "ºC")}

# The following list defines the columns that are likely to be used as
# exposure variables in a DLNM. If x_col starts with any of these strings
# and y_col does not, they are swapped to ensure that the exposure is
# continuous and the outcome is a count or rate.
LS_TARGET = ["mortality", "population"]


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
    x-lag cross-basis built from B-spline bases and estimate the
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
        Percentiles used to position internal knots for the X
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
        n_x x n_lag columns labelled cb_i_j.
    crossbasis_spec : dict
        Metadata needed for post-estimation tasks (knots, formulas, degrees,
        etc.).

    Notes
    -----
    * The cross-basis W is constructed as the Kronecker product of the
      X basis B(x_t) and the lag basis C(ell) and follows the
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
    # If "xcol" starts with a TARGET but "ycol" does not, swap them
    if any(x_col.startswith(ls) for ls in LS_TARGET) and not any(
        y_col.startswith(ls) for ls in LS_TARGET
    ):
        x_col, y_col = y_col, x_col
        if verbose:
            print(f"[INFO] Swapped x_col and y_col: now x_col={x_col}, y_col={y_col}")

    df = df[[x_col, y_col]].copy().dropna()

    # X spline basis specification
    knots = np.percentile(df[x_col], knots_percentiles)
    formula = f"bs(x, knots={list(knots)}, degree=2, include_intercept=False)"
    Z = dmatrix(formula, {"x": df[x_col]}, return_type="dataframe")
    Z.reset_index(drop=True, inplace=True)
    n_x = Z.shape[1]

    # Lag spline basis (time-invariant)
    if lag_knots is None:
        lag_knots = np.linspace(0, max_lag, min(4, max_lag + 1))[1:-1]
    lag_formula = f"bs(lag, knots={list(lag_knots)}, degree=2, include_intercept=False)"
    C = dmatrix(lag_formula, {"lag": np.arange(max_lag + 1)}, return_type="dataframe")
    C.index = np.arange(max_lag + 1)  # for easy lookup
    n_lag = C.shape[1]

    # Build cross-basis for every observation
    #     cb_{i}_{j}  where i = x basis, j = lag basis
    cross_cols = [f"cb_{i}_{j}" for j in range(n_lag) for i in range(n_x)]
    crossbasis_df = pd.DataFrame(0.0, index=df.index, columns=cross_cols)

    for ell in range(max_lag + 1):
        # X values at lag ell
        x_lag = df[x_col].shift(ell)
        # rows that became NaN because of the shift should be skipped
        valid = x_lag.notna()
        if not valid.any():
            continue

        basis_lag = dmatrix(
            formula, {"x": x_lag[valid]}, return_type="dataframe"
        ).to_numpy()  # (n_valid, n_x)
        w = C.loc[ell].to_numpy()  # (n_lag,)

        # Add contributions: Z_lag (n_valid x n_x) ⊗ w (n_lag,)
        kron_block = np.kron(w, basis_lag)  # (n_valid, n_x*n_lag)
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
        "formula": formula,
        "lag_formula": lag_formula,
        "knots": knots.tolist(),
        "lag_knots": list(lag_knots),
        "degree": 2,
        "lag_degree": 2,
        "n_x": n_x,
        "n_lag": n_lag,
        "max_lag": max_lag,
        "x_col": x_col,
        "y_col": y_col,
        # Preserve exposure range at fit time to build safe grids later
        "x_min": float(df[x_col].min()),
        "x_max": float(df[x_col].max()),
    }
    return model, crossbasis_df, spec


def generate_rr_curve(
    model: GLMResults,
    spline_spec: dict,
    xrange: tuple | None = None,
    max_lag: int = 3,
    ref_value: float | None = None,
    precision: float = 0.1,
) -> dict:
    """
    Generate the overall (lag-integrated) X-risk curve derived from a
    fitted DLNM.

    The function constructs the marginal cross-basis row
    ∑_ell C(ell) cx B(x) (i.e. integrates over lags) and combines it with the
    coefficient vector and its covariance to obtain point estimates and
    95 % confidence bands for the Relative Risk (RR) across a X grid.

    Parameters
    ----------
    model : statsmodels.genmod.generalized_linear_model.GLMResults
        GLM returned by fit_dlnm_weekly.
    spline_spec : dict
        Output crossbasis_spec from fit_dlnm_weekly.
    xrange : tuple
        Lower and upper bounds of the X grid in the same units as
        x_col. If None, the range is inferred from the data.
    max_lag : int
        Maximum lag (must match the value used at fitting time), by default 3.
    ref_value : float or None, default None
        X value at which RR = 1.  If None, the X with minimum estimated RR on
        the grid is used.
    precision : float, default 0.1
        Step size for the X grid, by default 0.1.

    Returns
    -------
    dict
        Dictionary containing the X grid, RR estimates, lower and upper
        confidence intervals, and the reference value.

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
    # Determine X grid bounds. Default to exposure range captured at fit time
    if xrange is None:
        xmin = floor(spline_spec.get("x_min", 0.0) - 1)
        xmax = ceil(spline_spec.get("x_max", 0.0) + 1)
    else:
        xmin, xmax = xrange

    # Ensure grid covers the internal knot locations to satisfy bs() bounds
    knots = np.array(spline_spec.get("knots", []), dtype=float)
    if knots.size:
        xmin = min(xmin, floor(float(knots.min())))
        xmax = max(xmax, ceil(float(knots.max())))

    # Build X grid & basis
    x_grid = np.arange(xmin, xmax + precision, precision)
    Zg = dmatrix(spline_spec["formula"], {"x": x_grid}, return_type="dataframe")
    n_x = Zg.shape[1]

    # Lag-basis rows & their sum (sum_lag c_k())
    C = dmatrix(
        spline_spec["lag_formula"],
        {"lag": np.arange(max_lag + 1)},
        return_type="dataframe",
    )
    lag_sum = C.sum(axis=0).to_numpy()  # (n_lag,)
    n_lag = lag_sum.size

    # Coefficient vector & covariance
    cross_names = [f"cb_{i}_{j}" for j in range(n_lag) for i in range(n_x)]
    beta = model.params[cross_names].to_numpy()
    V = model.cov_params().loc[cross_names, cross_names].to_numpy()

    # Helper to build cross-basis row = kron(lag_sum, Z_row)
    def cross_row(z_row: np.ndarray) -> np.ndarray:
        return np.kron(lag_sum, z_row)  # length n_x * n_lag

    # Compute log-RR & SE for the grid
    log_rr, se = [], []
    for z in Zg.to_numpy():
        s = cross_row(z)
        log_rr.append(s @ beta)
        se.append(np.sqrt(s @ V @ s))
    log_rr = np.array(log_rr)
    se = np.array(se)

    # Reference X
    if ref_value is None:
        idx_ref = np.argmin(np.exp(log_rr))
        ref_value = x_grid[idx_ref]
        ref_log_rr = log_rr[idx_ref]
    else:
        z_ref = dmatrix(
            spline_spec["formula"], {"x": [ref_value]}, return_type="dataframe"
        ).to_numpy()[0]
        ref_log_rr = cross_row(z_ref) @ beta

    # Normalise & exponentiate
    log_rr -= ref_log_rr

    # Get label and units for the x-axis
    label, units = DICT_LABELS.get(spline_spec["x_col"], (spline_spec["x_col"], ""))

    # Return as a dictionary
    return {
        "x_grid": x_grid.tolist(),
        "rr": np.exp(log_rr).tolist(),
        "rr_low": np.exp(log_rr - 1.96 * se).tolist(),
        "rr_high": np.exp(log_rr + 1.96 * se).tolist(),
        "ref_value": ref_value,
        "label": label,
        "units": units,
    }


def plot_rr_curve(
    model: GLMResults,
    spline_spec: dict,
    xrange: tuple,
    max_lag: int,
    ref_value: float | None = None,
    precision: float = 0.1,
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plot the overall (lag-integrated) X-risk curve derived from a
    fitted DLNM.

    The function constructs the marginal cross-basis row
    ∑_ell C(ell) cx B(x) (i.e. integrates over lags) and combines it with the
    coefficient vector and its covariance to obtain point estimates and
    95 % confidence bands for the Relative Risk (RR) across a X grid.

    Parameters
    ----------
    model : statsmodels.genmod.generalized_linear_model.GLMResults
        GLM returned by fit_dlnm_weekly.
    spline_spec : dict
        Output crossbasis_spec from fit_dlnm_weekly.
    xrange : tuple
        Lower and upper bounds of the X grid in the same units as
        x_col.
    max_lag : int
        Maximum lag (must match the value used at fitting time).
    ref_value : float or None, default None
        X value at which RR = 1.  If None, the X with minimum estimated RR on
        the grid is used.
    precision : float, default 0.1
        Step size for the X grid, by default 0.1.

    Returns
    -------
    fig : matplotlib.figure.Figure
        Figure object containing the plot.
    axs : matplotlib.axes.Axes
        Axes object containing the plot.

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
    dict_curve = generate_rr_curve(
        model,
        spline_spec,
        xrange=xrange,
        max_lag=max_lag,
        ref_value=ref_value,
        precision=precision,
    )
    x_grid = dict_curve["x_grid"]
    rr = dict_curve["rr"]
    ref_value = dict_curve["ref_value"]
    label = dict_curve["label"]
    units = dict_curve["units"]

    fig = plt.figure(figsize=(7, 4))
    axs = fig.add_subplot(111)
    axs.plot(x_grid, rr, color="darkred", lw=2)
    axs.axhline(1.0, ls="--", color="gray")
    axs.set_xlabel(f"{label} ({units})")
    axs.set_ylabel("Relative Risk (RR)")
    axs.set_title(f"Marginal RR vs {label} (ref = {ref_value:.1f} {units})")
    axs.grid(True, ls=":", lw=0.5)
    fig.tight_layout()
    return fig, axs


def main(
    file: str = "./data/europe.csv",
    code: str = "AT",
    x: str = "temp_era5_q50",
    y: str = "mortality_rate",
    fout: str = "output",
):
    # Load the dataset
    df = pd.read_csv(file)

    # Choose a code
    df = df[df["NUTS_ID"] == code]

    # Drop rows with NaNs in x or y columns
    df.dropna(subset=[x, y], inplace=True)

    # Create column "date" from "year" and "week"
    df["date"] = pd.to_datetime(
        df["year"].astype(str) + df["week"].astype(str) + "0", format="%Y%W%w"
    )

    # Set date as index
    df.set_index("date", inplace=True)

    # Print date range
    print(
        f"[INFO] Processing data for {code} from {df.index.min()} to {df.index.max()}"
    )

    # Fit the DLNM model
    model, spline_df, spline_spec = fit_dlnm_weekly(df, x, y)

    # Plot the relative risk curve
    fig, axs = plot_rr_curve(model, spline_spec, xrange=(-20, 40), max_lag=5)

    # Make sure the output directory exists
    path_out = Path(fout)
    path_out.mkdir(parents=True, exist_ok=True)
    # Save the plot
    fig.savefig(path_out / f"rr_curve_{code}.png", dpi=300)
    # Close
    plt.close(fig)


if __name__ == "__main__":
    typer.run(main)
