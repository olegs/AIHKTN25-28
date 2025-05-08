from urllib.parse import quote

import requests

from config import *
from pubtrends.data import AnalysisData
from sum_categories import summarize_categories
from sum_topics import summarize_topics


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


def make_summarize_model_sync_call(
        search_queries, job_id,
        summarized_data
):
    ex = AnalysisData.from_json(summarized_data)
    summaries_storage = {}
    try:
        summarize_categories(ex, summaries_storage)
        summarize_topics(ex, summaries_storage)
    except Exception as e:
        print(e)
        search_queries[job_id]['progress'][SUMMARIZE_STEP] = STEP_ERROR
        return
    search_queries[job_id][SUMMARIZE_STEP + "_RESULT"] = summaries_storage
    search_queries[job_id]['progress'][SUMMARIZE_STEP] = STEP_COMPLETE


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
