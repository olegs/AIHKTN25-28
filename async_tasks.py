import json
from urllib.parse import quote

import numpy as np
import requests

from pubtrends.data import AnalysisData
from config import *
from pubtrends.topics import get_topics_description


def start_summarize_async_step(search_queries, job_id):
    print("Starting summarize step")
    query = search_queries[job_id]['search_query']
    api_url = f"{PUBTRENDS_API}/get_result_api?jobid={job_id}&query={quote(query)}"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            # Make API call in a separate thread
            import threading
            thread = threading.Thread(target=make_summarize_model_sync_call,
                                      args=(search_queries, job_id, data))
            thread.daemon = True
            thread.start()
            return
    except Exception as e:
        print(e)
    # Else mark as error
    search_queries[job_id]['progress'][SUMMARIZE_STEP] = STEP_ERROR


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


def make_summarize_model_sync_call(
        search_queries, job_id,
        summarized_data
):
    ex = AnalysisData.from_json(summarized_data)
    try:
        summarized_categories = summarize_categories(ex)
        topics_summary = summarize_topics(data=ex)
    except Exception as e:
        print(e)
        search_queries[job_id]['progress'][SUMMARIZE_STEP] = STEP_ERROR
        return
    search_queries[job_id][SUMMARIZE_STEP + "_RESULT"] = summarized_categories
    search_queries[job_id][SUMMARIZE_STEP + "_RESULT2"] = topics_summary
    search_queries[job_id]['progress'][SUMMARIZE_STEP] = STEP_COMPLETE


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


def start_semantic_search_async_step(search_queries, job_id):
    print("Starting semantic search step")
    query = search_queries[job_id]['search_query']
    # Make API call in a separate thread
    import threading
    thread = threading.Thread(target=make_semantic_search_sync_call,
                              args=(query, search_queries, job_id))
    thread.daemon = True
    thread.start()


def make_semantic_search_sync_call(query, search_queries, job_id):
    try:
        # Make the POST request with abstracts and si_mode
        response = requests.get(f"{GOOGLE_SEMANTIC_SEARCH_ENDPOINT}?user_input={query}")
        # Handle response
        if response.status_code == 200:
            response = response.json()
            search_queries[job_id][SEMANTIC_SEARCH_STEP + "_RESULT"] = response
            search_queries[job_id]['progress'][SEMANTIC_SEARCH_STEP] = STEP_COMPLETE
            return
    except Exception as e:
        print(e)
    search_queries[job_id]['progress'][SEMANTIC_SEARCH_STEP] = STEP_ERROR


def _render_topic_html(topic_name, keyword_based_title, summary):
    return [
        "<tr>",
        "<td style='padding: 1em; border-bottom: 1px solid #ccc; text-align: left;'>",
        f"<h3 style='margin: 0 0 0.5em 0; font-weight: normal;'>Topic {topic_name}</h3>",
        f"<p style='margin: 0 0 0.5em 0;'><strong>{keyword_based_title}</strong></p>",
        "<hr style='border: none; border-top: 1px solid #ccc;'/>",
        convert_to_html(summary),
        "<hr style='border: none; border-top: 1px dashed #ccc;'/>",
        "</td>",
        "</tr>",
    ]


def summarize_topics(
        *,
        data,
        topic_description_words=10,
        force_topic_name=None,
        as_html: bool = True
):
    preferred_count_per_topic = 50
    connectivity_percentile_thr = 50

    pubmed_cluster_names = sorted(data.df.comp.unique())

    topics_keywords = get_topics_description(
        data.df,
        data.corpus, data.corpus_tokens, data.corpus_counts,
        n_words=topic_description_words
    )

    output = []
    if as_html:
        output.append('<table style="width:100%; border-collapse: collapse;">')

    for topic_name in pubmed_cluster_names:
        if (force_topic_name is not None) and (topic_name != force_topic_name):
            continue

        print(f"Processing topic {topic_name}")

        topic_data = prepare_abstracts_for_topic(
            data, topic_name,
            connectivity_percentile_thr=connectivity_percentile_thr,
            preferred_count_per_topic=preferred_count_per_topic
        )

        summary = prompt_summarize_abstracts(topic_data)

        if summary:
            topic_summary_data = {
                "summary": summary,
                "topics_keywords": [k for k, v in topics_keywords[topic_name]],
            }
            keyword_based_title = prompt_assign_title_to_summary(topic_summary_data)
        else:
            keyword_based_title = ""

        # Render per topic
        if as_html:
            output.extend(_render_topic_html(int(topic_name)+1, keyword_based_title, summary))
        else:
            output.extend(_render_topic_plain(int(topic_name)+1, keyword_based_title, summary))

    if as_html:
        output.append("</table>")
        return "\n".join(output)  # HTML-safe string
    else:
        return "\n".join(output)

