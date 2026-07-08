import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.stats import chi2

def compare_marginals(
    synthetic_df,
    input_marginal,
    groupby_cols,
    input_label="Input",
    output_label="Synthetic",
    title="Comparison of Distribution",
    xticks_labels=None,
    normalize=True,
    ax=None
):
    """
    Plot 2 marginal distributions in a normalized space
    
    Parameters:
    - synthetic_df: pd.DataFrame, the synthetic population
    - input_marginal: np.ndarray or pd.Series, the input marginal
    - groupby_cols: str or list of str, column in synthetic_df to group by
    - input_label: str, label for input marginal
    - output_label: str, label for synthetic marginal
    - title: str, plot title
    - xticks_labels: list, optional, labels for x-axis ticks
    - normalize: bool, whether to normalize or plot counts
    - ax: Which subplot of the given ax to plot to. 
    If none, creates a new figure for each plot

    Explanation:

    To effectively count the number of people in each categorical value,
    groupby is used. 
    """

    if isinstance(groupby_cols, str):
        groupby_cols = [groupby_cols]
    if len(groupby_cols) > 1:
        print(f'1 groupby column only! {len(groupby_cols)} were given.')
        return None
    output_counts = synthetic_df.groupby(groupby_cols).size()
    output_counts = output_counts.sort_index()

    if normalize:
        output_marginal = output_counts / output_counts.sum()
        input_marginal = np.array(input_marginal, dtype=float)
        input_marginal = input_marginal / input_marginal.sum()

    else:
        output_marginal = output_counts
        input_marginal = np.array(input_marginal, dtype=float)

    if ax is None:
        fig, ax = plt.subplots(figsize=(10,5))
    else:
        fig = ax.figure

    ax.plot(range(len(input_marginal)), input_marginal, label=input_label, marker='o')
    ax.plot(range(len(output_marginal)), output_marginal, label=output_label, marker='x')
    ax.set_xlabel(" x ".join(groupby_cols))
    ax.set_ylabel("Proportion" if normalize else "Count")
    ax.set_title(title)
    ax.legend()
    ax.grid(True)
    # set integer x-ticks only
    num_ticks = max(len(input_marginal), len(output_marginal))
    ax.set_xticks(range(num_ticks))
    if xticks_labels is not None:
        ax.set_xticks(range(len(xticks_labels)))
        ax.set_xticklabels(xticks_labels, rotation=45)
    fig.tight_layout()
    return fig, ax

def compare_2d_marginals_heatmap(
    synthetic_df,
    input_joint,
    groupby_cols,
    input_label="Input",
    output_label="Synthetic",
    title="Comparison of 2D Distribution",
    normalize=True,
    ax=None
):
    """
    Plot 2D joint distribution heatmaps of input and synthetic data

    Parameters:
    - synthetic_df: pd.DataFrame, the synthetic population
    - input_joint: 2D np.ndarray or nested list (joint distribution of the input).
    - groupby_cols: list of 2 strings, column names for 2D joint.
    - input_label: str, label for input heatmap.
    - output_label: str, label for synthetic heatmap.
    - title: str, plot title.
    - normalize: bool, whether to normalize both histograms to proportions.
    - ax: list of 2 axes (for subplots). 
    If none to create new.

    Returns:
    - fig, [ax_input, ax_output]
    """

    if not isinstance(groupby_cols, (list, tuple)) or len(groupby_cols) != 2:
        raise ValueError("groupby_cols must be a list of 2 column names.")

    # Compute 2D histogram from synthetic_df
    output_counts = synthetic_df.groupby(groupby_cols).size().unstack(fill_value=0)
    output_array = output_counts.to_numpy()

    input_array = np.array(input_joint, dtype=float)

    if input_array.shape != output_array.shape:
        input_array = input_array.T # flip

    if normalize:
        input_array = input_array / input_array.sum()
        output_array = output_array / output_array.sum()

    if ax is None:
        fig, axs = plt.subplots(1, 2, figsize=(12, 5))
    else:
        axs = ax
        fig = axs[0].figure

    im0 = axs[0].imshow(input_array, cmap='plasma', origin='lower', aspect='auto')
    axs[0].set_title(f"{input_label} Distribution")
    fig.colorbar(im0, ax=axs[0])

    im1 = axs[1].imshow(output_array, cmap='plasma', origin='lower', aspect='auto')
    axs[1].set_title(f"{output_label} Distribution")
    fig.colorbar(im1, ax=axs[1])

    for ax_i in axs:
        ax_i.set_xlabel(groupby_cols[1])
        ax_i.set_ylabel(groupby_cols[0])
        ax_i.grid(False)

    fig.suptitle(title)
    fig.tight_layout()
    return fig, axs


def dataframe_chisquare_proportions_manual(synthetic_df_to_compare, input_distribution, debug=False, smoothing=1e-5):
    '''
    Chi-square test handling missing bins by alignment and smoothing zero expected counts.

    Parameters:
    - synthetic_df_to_compare: pd.Series (numerical categories)
    - input_distribution: pd.Series, dict, or np.array (expected counts)
    - debug: bool
    - smoothing: small float to replace zero expected counts

    Returns:
    - chi2_stat, p_value

    Notes:
    - Function assumes input distribution is in categorical order
    - Function assumes synthetic df's values are 0->n
    '''
    # Get observed counts and sort by index
    observed = synthetic_df_to_compare.value_counts().sort_index()
    
    # Convert input_distribution to Series if not already
    if not isinstance(input_distribution, pd.Series):
        try:
            input_distribution = pd.Series(input_distribution)
        except Exception:
            raise ValueError("input_distribution must be convertible to pd.Series")

    # Input is in categorical order. Remove original indexes (non numerical most of the time)
    # Done for alignment with output categorical 
    expected = input_distribution.reset_index(drop=True)

    # Align bins: union of all indexes
    all_bins = observed.index.union(expected.index)

    observed = observed.reindex(all_bins, fill_value=0)
    expected = expected.reindex(all_bins, fill_value=0)

    if debug:
        print("Aligned observed:", observed)
        print("Aligned expected:", expected)

    # Scale expected to total observed count
    total_observed = observed.sum()
    expected_scaled = expected / expected.sum() * total_observed

    # Replace zeros in expected_scaled by smoothing small value
    expected_scaled = expected_scaled.replace(0, smoothing)

    # Optional: Replace zeros in observed by smoothing (usually not needed)
    # observed = observed.replace(0, smoothing)

    if debug:
        print("Scaled expected (with smoothing):", expected_scaled)

    # Calculate chi2 statistic
    chi2_stat = np.sum((observed - expected_scaled) ** 2 / expected_scaled)

    dof = len(all_bins) - 1

    p_value = chi2.sf(chi2_stat, dof)

    return chi2_stat, p_value