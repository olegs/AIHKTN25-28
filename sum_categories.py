import json

import numpy as np
import pandas as pd
import requests
from tornado import concurrent

from config import GOOGLE_SUMMARIZE_CATEGORY_GENES, GOOGLE_SUMMARIZE_CATEGORY_SUBSTANCES, \
    GOOGLE_SUMMARIZE_CATEGORY_CONDITIONS, GOOGLE_SUMMARIZE_CATEGORY_PROTEINS, GOOGLE_SUMMARIZE_CATEGORIES_ENDPOINT


def summarize_categories(ex, summaries_storage):
    highly_connected_df, abstracts_json = preprocess_summarize_categories(ex)
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # System prompt enum (must match server-side allowed value), here are represented all types
            for si_mode in [GOOGLE_SUMMARIZE_CATEGORY_GENES,
                            GOOGLE_SUMMARIZE_CATEGORY_SUBSTANCES,
                            GOOGLE_SUMMARIZE_CATEGORY_CONDITIONS,
                            GOOGLE_SUMMARIZE_CATEGORY_PROTEINS]:
                # Submit all batches to the executor
                futures.append(executor.submit(
                    summarize_category_and_save,
                    abstracts_json, highly_connected_df, si_mode, summaries_storage
                ))
    # Process results as they complete
    for _ in concurrent.futures.as_completed(futures):
        pass



def summarize_category_and_save(abstracts_json, highly_connected_df, si_mode, summaries_storage):
    summarized_data = summarize_entities(si_mode, abstracts_json)
    connections_by_pid = dict(zip(highly_connected_df['id'], highly_connected_df['connections']))
    summaries_storage[si_mode] = (connections_by_pid, summarized_data)


def preprocess_summarize_categories(ex):
    dfs = []
    for c in sorted(ex.df.comp.unique()):
        filtered_df = ex.df[ex.df.comp == c]
        highly_connected_df = filter_by_connectivity(
            filtered_df,
            ex.papers_graph,
            percentile=80,
            max_count=5
        )
        dfs.append(highly_connected_df)
    highly_connected_df = pd.concat(dfs).reset_index(drop=True)

    abstract_entries = highly_connected_df[['id', 'abstract']].to_dict(orient='records')
    # Convert to formatted string for LLM
    abstracts_json = json.dumps(abstract_entries, ensure_ascii=False, indent=2)
    return highly_connected_df, abstracts_json


def summarize_entities(si_mode, abstracts_json):
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
        print(f"✅{si_mode} Entities Extracted")
        return summarized_data
    return None


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


def prepare_entities_summary(entities):
    entities_summary = []
    for idx, entity in enumerate(sorted(entities, key=lambda g: g['total_connections'], reverse=True), start=1):
        collapse_id = f"collapse-{idx}"
        paper_links = "<br>".join(
            f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pid}" target="_blank">PMID: {pid}</a>' for pid in entity["cited_in"]
        )
        # idx, entity_name, entity_context, entity_total_connections, paper_links, entities_len, collapse_id
        entities_summary.append((
            idx,
            entity['name'],
            entity['context'],
            entity['total_connections'],
            paper_links,
            len(entity['cited_in']),
            collapse_id))
    return entities_summary
