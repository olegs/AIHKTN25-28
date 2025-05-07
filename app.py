from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    search_query = ""
    search_results = []
    search_type = "text"

    if request.method == 'POST':
        search_query = request.form.get('search_query', '')
        search_type = request.form.get('search_type', 'text')

        # In a real application, you would implement actual search logic here
        # For now, we'll just return placeholder messages
        if search_query:
            if search_type == 'semantic':
                search_results = [
                    f"Semantic search result 1 for: {search_query}",
                    f"Semantic search result 2 for: {search_query}",
                    f"Semantic search result 3 for: {search_query}"
                ]
            else:
                search_results = [
                    f"Text search result 1 for: {search_query}",
                    f"Text search result 2 for: {search_query}",
                    f"Text search result 3 for: {search_query}"
                ]

    return render_template('index.html', 
                          search_query=search_query, 
                          search_results=search_results,
                          search_type=search_type)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, extra_files=['templates/'], port=5003)
