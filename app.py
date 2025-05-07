import os

from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
from urllib.parse import quote
import json


PUBTRENDS_API = os.getenv("PUBTRENDS_API", "http://172.16.192.63:5000")

app = Flask(__name__)

# In-memory storage for job status and results
# In a production environment, this should be replaced with a proper database
search_queries = {}

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
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
            search_queries[job_id] = search_query
            return redirect(url_for('progress', job_id=job_id))
        else:
            return "Failed to make API call to PubTrends"
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
    except:
        return None

@app.route('/progress/<job_id>')
def progress(job_id):
    if job_id not in search_queries:
        return redirect(url_for('index'))
    return render_template('progress.html',
                           job_id=job_id,
                           search_query=search_queries[job_id])

@app.route('/check_status/<job_id>')
def check_status(job_id):
    # TODO: add better error processing
    if job_id not in search_queries:
        return {'status': 'not_found'}
    try:
        api_url = f"{PUBTRENDS_API}/check_status_api/{job_id}"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success':
                return {'status': 'success'}
            elif data['status'] == 'failed':
                return {'status': 'failed'}

        return {'status': 'pending'}
    except:
        return {'status': 'failed'}

@app.route('/results/<job_id>')
def results(job_id):
    if job_id not in search_queries:
        return "Result not found"
    try:
        query = search_queries[job_id]
        api_url = f"{PUBTRENDS_API}/get_result_api?jobid={job_id}&query={quote(query)}"
        response = requests.get(api_url)
        if response.status_code == 200:
            data = response.json()
            return f"Successfully got a json response!!! {json.dumps(data, indent=2)}"
        return "Something went wrong"
    except:
        return "Error occurred", 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, extra_files=['templates/'], port=5003)
