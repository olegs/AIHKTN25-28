import json
from urllib.parse import quote

import numpy as np
import requests

from pubtrends.data import AnalysisData
from util import PUBTRENDS_API, GOOGLE_SUMMARIZE_CATEGORIES_ENDPOINT, SUMMARIZE_STEP, STEP_COMPLETE, STEP_ERROR


def start_summarize_async_step(search_queries, pubtrends_job_id):
    print("Starting summarize step")
    query = search_queries[pubtrends_job_id]['search_query']
    api_url = f"{PUBTRENDS_API}/get_result_api?jobid={pubtrends_job_id}&query={quote(query)}"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            # Make API call in a separate thread
            import threading
            thread = threading.Thread(target=make_summarize_model_sync_call,
                                      args=(search_queries, pubtrends_job_id, data))
            thread.daemon = True
            thread.start()
            return
    except Exception as e:
        print(e)
    # Else mark as error
    search_queries[pubtrends_job_id]['progress'][SUMMARIZE_STEP] = STEP_ERROR


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


def render_table(entities):
    html = """
    <style>
        .collapse-content { display: none; margin-top: 5px; }
        .toggle-button { cursor: pointer; color: blue; text-decoration: underline; }
        th { text-align: left; }
    </style>
    <script>
        function toggleCollapse(id) {
            var x = document.getElementById(id);
            x.style.display = (x.style.display === "none") ? "block" : "none";
        }
    </script>
    <table border="1" style="border-collapse: collapse; width: 100%;">
        <thead>
            <tr>
                <th>#</th>
                <th>Name</th>
                <th>Context</th>
                <th>Total Connections</th>
                <th>Papers</th>
            </tr>
        </thead>
        <tbody>
    """
    for idx, entity in enumerate(sorted(entities, key=lambda g: g['total_connections'], reverse=True), start=1):
        collapse_id = f"collapse-{idx}"
        paper_links = "<br>".join(
            f'<a href="/paper/{pid}" target="_blank">{pid}</a>' for pid in entity["cited_in"]
        )
        entities_len = len(entity['cited_in'])
        html += f"""
        <tr>
            <td>{idx}</td>
            <td>{entity['name']}</td>
            <td>{entity['context']}</td>
            <td>{entity['total_connections']}</td>
            <td>
                <span class="toggle-button" onclick="toggleCollapse('{collapse_id}')">
                    Show Papers ({entities_len})
                </span>
                <div id="{collapse_id}" class="collapse-content">{paper_links}</div>
            </td>
        </tr>
        """
    html += "</tbody></table>"
    return html


def make_summarize_model_sync_call(
        search_queries, pubtrends_job_id,
        summarized_data
):
    ex = AnalysisData.from_json(summarized_data)
    highly_connected_df = filter_by_connectivity(
        ex.df,
        ex.papers_graph,
        percentile=90,
        max_count=50  # cap the result if it's too large
    )

    abstract_entries = highly_connected_df[['id', 'abstract']].to_dict(orient='records')

    # Convert to formatted string for LLM
    abstracts_json = json.dumps(abstract_entries, ensure_ascii=False, indent=2)

    # System prompt enum (must match server-side allowed value), here are represented all types
    si_mode = "GENES_EXTRACTION"
    # si_mode = "SUBSTANCES_EXTRACTION"
    # si_mode = "CONDITIONS_EXTRACTION"
    # si_mode = "PROTEINS_EXTRACTION"

    # Make the POST request with abstracts and si_mode
    try:
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
            print("✅ Entities Extracted:")
            search_queries[pubtrends_job_id][SUMMARIZE_STEP + "_RESULT"] = summarized_data
            search_queries[pubtrends_job_id]['progress'][SUMMARIZE_STEP] = STEP_COMPLETE
            return
    except Exception as e:
        print(e)
        search_queries[pubtrends_job_id]['progress'][SUMMARIZE_STEP] = STEP_ERROR
