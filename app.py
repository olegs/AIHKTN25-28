import os
import time

from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
from urllib.parse import quote
from async_tasks import start_summarize_async_step
from util import PUBTRENDS_API, STEP_COMPLETE, PUBTRENDS_STEP, START_STEP, STEP_NOT_STARTED, STEP_PENDING, \
    SUMMARIZE_STEP, STEP_ERROR, create_text_steps

app = Flask(__name__)

# In-memory storage for job status and results
# In a production environment, this should be replaced with a proper database
search_queries = {}

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    cleanup_old_jobs()
    search_query = request.form.get('search_query', '')
    search_type = request.form.get('search_type', 'text')

    if not search_query:
        return render_template('results.html', 
                              search_query=search_query, 
                              search_results=[],
                              search_type=search_type)

    if search_type == 'text':
        job_id = make_pubtrends_api_call(search_query)
        if job_id:
            search_queries[job_id] = dict(search_query=search_query,
                                          job_id=job_id,
                                          progress=create_text_steps(),
                                          timestamp=time.time())
            return redirect(url_for('progress', job_id=job_id))
        else:
            return render_template('error.html', "Failed to make API call to PubTrends")
    else:
        # For semantic search, use the existing placeholder
        search_results = ["Not implemented yet"]
        return render_template('results.html', 
                              search_query=search_query, 
                              search_results=search_results,
                              search_type=search_type)




def make_pubtrends_api_call(search_query):
    # TODO: add better error processing
    try:
        api_url = f"{PUBTRENDS_API}/search_terms_api"
        response = requests.post(api_url, data={
            'query': search_query,
        })
        if response.status_code == 200:
            # Store the response data
            data = response.json()
            if data['success']:
                return data['jobid']
        return None
    except Exception as e:
        print(e)
        return None

@app.route('/progress/<job_id>')
def progress(job_id):
    cleanup_old_jobs()
    if job_id not in search_queries:
        return redirect(url_for('index'))
    return render_template('progress.html',
                           job_id=job_id,
                           search_query=search_queries[job_id]['search_query'])




@app.route('/check_status/<job_id>')
def check_status(job_id):
    # TODO: add better error processing
    if job_id not in search_queries:
        return {'status': 'not_found'}
    progress = search_queries[job_id]['progress']
    for v in progress.values():
        if v == STEP_ERROR:
            return {'status': 'failed'}
    try:
        api_url = f"{PUBTRENDS_API}/check_status_api/{job_id}"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            progress[START_STEP] = STEP_COMPLETE
            if progress[PUBTRENDS_STEP] == STEP_NOT_STARTED:
                progress[PUBTRENDS_STEP] = STEP_PENDING
            if data['status'] == 'success':
                progress[PUBTRENDS_STEP] = STEP_COMPLETE
                if progress[SUMMARIZE_STEP] == STEP_NOT_STARTED:
                    progress[SUMMARIZE_STEP] = STEP_PENDING
                    # Submit task async and wait till it will eventually becomes STEP_COMPLETE STATUS
                    start_summarize_async_step(search_queries, job_id)
                elif progress[SUMMARIZE_STEP] == STEP_COMPLETE:
                    return {'status': 'success', 'progress': list(progress.items())}
            elif data['status'] == 'failed':
                return {'status': 'failed'}
        return {'status': STEP_PENDING, 'progress': list(progress.items())}
    except Exception as e:
        print(e)
        return {'status': 'failed'}

@app.route('/results/<job_id>')
def results(job_id):
    if job_id not in search_queries:
        return render_template('error.html', message="Result not found")
    try:
        query = search_queries[job_id]['search_query']
        pubtrends_url = f"{PUBTRENDS_API}/result?query={quote(query)}" \
              f"&source=Pubmed&limit=1000&sort=most_cited&noreviews=on&min_year=&max_year=&jobid={job_id}"
        genes_summaries = []
        entities = search_queries[job_id][SUMMARIZE_STEP + "_RESULT"]
        for idx, entity in enumerate(sorted(entities, key=lambda g: g['total_connections'], reverse=True), start=1):
            collapse_id = f"collapse-{idx}"
            paper_links = "<br>".join(
                f'<a href="/paper/{pid}" target="_blank">{pid}</a>' for pid in entity["cited_in"]
            )
            # idx, entity_name, entity_context, entity_total_connections, paper_links, entities_len, collapse_id
            genes_summaries.append((
                idx,
                entity['name'],
                entity['context'],
                entity['total_connections'],
                paper_links,
                len(entity['cited_in']),
                collapse_id))
        return render_template(
            "results.html",
            search_query=query,
            pubtrends_result=pubtrends_url,
            genes_summaries=genes_summaries)
    except Exception as e:
        print(e)
        return render_template('error.html', message="Exception occurred")

@app.route('/error')
def error():
    return render_template('error.html', message="Something went wrong")


# Clean up old jobs periodically (in a production environment, this would be a scheduled task)
def cleanup_old_jobs():
    current_time = time.time()
    for job_id in list(search_queries.keys()):
        # Remove jobs older than 1 hour
        if current_time - search_queries[job_id]['timestamp'] > 3600:
            if job_id in search_queries:
                del search_queries[job_id]
            del search_queries[job_id]

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, extra_files=['templates/'], port=5003)
