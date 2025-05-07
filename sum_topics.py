import numpy as np
import requests
import re
import html

from config import GOOGLE_MODEL_SUMMARIZE_TOPIC_TITLE_ENDPOINT, GOOGLE_MODEL_SUMMARIZE_TOPIC_ENDPOINT
from pubtrends.topics import get_topics_description


def summarize_topics(
        *,
        data,
        topic_description_words=10,
        force_topic_name=None,
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
        name = int(topic_name) + 1
        output.append((name, keyword_based_title, convert_to_html(summary)))
    return output


def prepare_abstracts_for_topic(data, topic_name, *, preferred_count_per_topic, connectivity_percentile_thr):
    filtered_df = data.df[data.df.comp == topic_name]

    highly_connected_df = filter_by_connectivity(
        filtered_df,
        data.papers_graph,
        percentile=connectivity_percentile_thr,
        preferred_count=preferred_count_per_topic
    )
    abstract_entries = highly_connected_df[['id', 'abstract']].to_dict(orient='records')

    topic_data = {
        'abstracts': abstract_entries
        # 'abstracts': abstract_entries[0:2] # XXX: Playground
    }

    print(f"Highly connected papers: {len(filtered_df)} -> {len(highly_connected_df)}")

    return topic_data


def filter_by_connectivity(df, graph, percentile=75, preferred_count=None):
    # Step 1: Compute connectivity (without modifying df)
    connectivity = df['id'].apply(lambda pid: len(list(graph.neighbors(pid))))

    # Step 2: Compute the percentile threshold
    if len(df) <= preferred_count:
        # If few elements => TAKE all
        threshold = np.nanmin(connectivity)
    else:
        # If need to limit => limit by percentile, but not lower than preferred_count
        threshold = min(np.percentile(connectivity, percentile),
                        sorted(connectivity, reverse=True)[preferred_count - 1])

    # Step 3: Get mask for nodes above threshold
    above_threshold_mask = connectivity >= threshold

    # print(f"len(df) = {len(df)}, threshold = {threshold}, {percentile}-th : {np.percentile(connectivity, percentile)}")
    # print(sorted(connectivity, reverse=True))
    # print("---")

    # Step 4: Apply the mask
    filtered_df = df[above_threshold_mask].copy()
    filtered_df['connections'] = connectivity[above_threshold_mask].values

    # Step 5: If max_count is specified, take top N by connections
    if (preferred_count is not None) and len(filtered_df) > preferred_count:
        filtered_df = filtered_df.sort_values('connections', ascending=False).head(preferred_count)

    return filtered_df


def prompt_summarize_abstracts(topic_data):
    response = requests.post(
        f"{GOOGLE_MODEL_SUMMARIZE_TOPIC_TITLE_ENDPOINT}",
        json=topic_data,  # XXX Pass Python object here, not dump
        # json=json.dumps(topic_data, ensure_ascii=False, indent=2),
        headers={"Content-Type": "application/json"}
    )

    # 5. Handle response
    if response.status_code == 200:
        data = response.json()

        if "summary" in data:
            return data["summary"]

        print(f"❌ Error: No summary in response")
    else:
        print(f"❌ Error: {response.status_code}")

    return ""


def prompt_assign_title_to_summary(topic_summary_data):
    response = requests.post(
        f"{GOOGLE_MODEL_SUMMARIZE_TOPIC_ENDPOINT}",
        json=topic_summary_data,
        headers={"Content-Type": "application/json"}
    )

    # Handle response
    if response.status_code == 200:
        data = response.json()

        if "title" in data:
            return data["title"]

        print(f"❌ Error: No title in response")
    else:
        print(f"❌ Error: {response.status_code}")

    return ""



def convert_to_html(text):
    # Step 1: Escape HTML special characters
    text = html.escape(text)

    # Step 2: Replace PMID references with links
    text = re.sub(
        r'PMID=(\d+)',
        r'<a href="https://pubmed.ncbi.nlm.nih.gov/\1" target="_blank">PMID: \1</a>',
        text
    )

    # Step 3: Convert double newlines or newlines to <p> blocks
    paragraphs = re.split(r'\n\s*\n|\n', text)
    html_paragraphs = [f"<p>{para.strip()}</p>" for para in paragraphs if para.strip()]

    return "\n".join(html_paragraphs)
