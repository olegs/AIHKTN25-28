import functions_framework
from google.cloud import bigquery
import os
from flask import jsonify

PROJECT_ID = os.environ.get('GCP_PROJECT') or 'aihktn25-28'
# Number of ids returned by the vector search
NUM_OF_IDS = 1000

client = bigquery.Client(project=PROJECT_ID)

@functions_framework.http
def semantic_search(request):
    """HTTP Cloud Run lambda architecture function to perform vector search based 
    semantic search on user input."""
    
    request_json = request.get_json(silent=True)
    request_args = request.args

    if request_json and 'user_input' in request_json:
        user_input = request_json['user_input']
    elif request_args and 'user_input' in request_args:
        user_input = request_args['user_input']
    else:
        return "Missing 'user_input' parameter.", 400

    try:
        embeddings_query_query = f"""
        CREATE OR REPLACE TABLE `aihktn25-28.dataset_eu_test.embeddings_query` AS
          SELECT * FROM ML.GENERATE_EMBEDDING(
            MODEL `aihktn25-28.dataset_eu_test.embedding_model002`,
            (
              SELECT @user_input AS content
            )
          )
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_input", "STRING", user_input)
            ]
        )
        client.query(embeddings_query_query, job_config=job_config).result()

        vector_search_query = f"""
        SELECT base.id, distance
        FROM
        VECTOR_SEARCH(
            TABLE `dataset_eu_test.embeddings_table`, 'ml_generate_embedding_result',
            TABLE `dataset_eu_test.embeddings_query`, 'ml_generate_embedding_result',
            top_k => {NUM_OF_IDS},
            distance_type => 'COSINE'
        )
        ORDER BY distance ASC;
        """
        results = client.query(vector_search_query).result()

        response_data = []

        for row in results:
            id = row["id"]
            entry = id

            if len(response_data) > NUM_OF_IDS:
                break

            response_data.append(entry)

        return jsonify(response_data)

    except Exception as e:
        return f"Error: {str(e)}", 500
