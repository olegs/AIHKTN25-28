import json

import numpy as np
import requests

from config import GOOGLE_SUMMARIZE_CATEGORY_GENES, GOOGLE_SUMMARIZE_CATEGORY_SUBSTANCES, \
    GOOGLE_SUMMARIZE_CATEGORY_CONDITIONS, GOOGLE_SUMMARIZE_CATEGORY_PROTEINS, GOOGLE_SUMMARIZE_CATEGORIES_ENDPOINT


def summarize_categories(ex):
    highly_connected_df = filter_by_connectivity(
        ex.df,
        ex.papers_graph,
        percentile=90,
        max_count=50  # cap the result if it's too large
    )
    abstract_entries = highly_connected_df[['id', 'abstract']].to_dict(orient='records')
    # Convert to formatted string for LLM
    abstracts_json = json.dumps(abstract_entries, ensure_ascii=False, indent=2)
    summarized_categories = {}
    # System prompt enum (must match server-side allowed value), here are represented all types
    for si_mode in [GOOGLE_SUMMARIZE_CATEGORY_GENES,
                    GOOGLE_SUMMARIZE_CATEGORY_SUBSTANCES,
                    GOOGLE_SUMMARIZE_CATEGORY_CONDITIONS,
                    GOOGLE_SUMMARIZE_CATEGORY_PROTEINS]:
        print(f"Summarizing category {si_mode}...")
        # Make the POST request with abstracts and si_mode
        response = requests.post(
            f"{GOOGLE_SUMMARIZE_CATEGORIES_ENDPOINT}?si_mode={si_mode}",
            json=abstracts_json,
            headers={"Content-Type": "application/json"}
        )
        # Handle response
        if response.status_code == 200:
            summarized_data = response.json()
            connections_by_pid = dict(zip(highly_connected_df['id'], highly_connected_df['connections']))
            for entity in summarized_data:
                entity["total_connections"] = sum(
                    connections_by_pid.get(pid, 0) for pid in entity.get("cited_in", [])
                )
            summarized_categories[si_mode] = summarized_data
            print(f"✅{si_mode} Entities Extracted")
    return summarized_categories

def filter_by_connectivity(df, graph, percentile=75, max_count=None):
    # Step 1: Compute connectivity (without modifying df)
    connectivity = df['id'].apply(lambda pid: len(list(graph.neighbors(pid))))

    # Step 2: Compute the percentile threshold
    threshold = np.percentile(connectivity, percentile)

    # Step 3: Get mask for nodes above threshold
    above_threshold_mask = connectivity >= threshold

    # Step 4: Apply the mask
    filtered_df = df[above_threshold_mask].copy()
    filtered_df['connections'] = connectivity[above_threshold_mask].values

    # Step 5: If max_count is specified, take top N by connections
    if max_count is not None and len(filtered_df) > max_count:
        filtered_df = filtered_df.sort_values('connections', ascending=False).head(max_count)

    return filtered_df
