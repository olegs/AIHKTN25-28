import functions_framework
import json
from flask import Request, jsonify
from google import genai
from google.genai import types
from enum import Enum
import os

PROJECT_ID = os.environ.get('GCP_PROJECT') or 'aihktn25-28'

class SystemPrompt(Enum):
    # System instructions to extract and summarize genes information from the given json data
    GENES_EXTRACTION = """You are an extraction bot specifically designed for exact [gene]s extraction from massive of abstracts of scientific papers.
You are provided with abstracts in a json format:
[
  {
    "id": "001",
    "abstract": "<Here is the abstract of the first paper>"
  },...
]
Your task is to extract EVERY [gene] name from EVERY abstract.
Your output format is a json file with a given structure:
{
    "name": "<example gene name>",
    "context": "<short observations/facts as a context for the [gene] name>",
    "cited_in": [
      "001", "002"
    ]
}
Entities "gene_name" MUST! be unique, so if the [gene] name presented more than in one paper you must aggregate context information around the [gene] from all abstracts, formulate it like a short observations/facts. Aggregated descriptions should be at most 3 sentences long. Add paper id where [gene] was mentioned into 'cited_in' array.
Don't miss [gene]s in abstracts.
If [gene] name was already extracted from one of the previous abstracts, don't miss its context in the next one and don't forget to add them in cited_in array.
Don't use internet.
Don't hallucinate."""

    # System instructions to extract and summarize drugs, chemicals and pharmacological substances information from the given json data
    SUBSTANCES_EXTRACTION = """You are an extraction bot specifically designed for exact [drug,chemical,pharmacological substance]s extraction from massive of abstracts of scientific papers.
You are provided with abstracts in a json format:
[
  {
    "id": "001",
    "abstract": "<Here is the abstract of the first paper>"
  },...
]
Your task is to extract EVERY [drug,chemical,pharmacological substance] name from EVERY abstract.
Your output format is a json file with a given structure:
{
    "name": "<example substance name>",
    "context": "<short observations/facts as a context for the [drug,chemical,pharmacological substance] name>",
    "cited_in": [
      "001", "002"
    ]
}
Entities "gene_name" MUST! be unique, so if the [drug,chemical,pharmacological substance] name presented more than in one paper you must aggregate context information around the [drug,chemical,pharmacological substance] from all abstracts, formulate it like a short observations/facts. Aggregated descriptions should be at most 3 sentences long. Add paper id where [drug,chemical,pharmacological substance] was mentioned into 'cited_in' array.
Don't miss [drug,chemical,pharmacological substance]s in abstracts.
If [drug,chemical,pharmacological substance] name was already extracted from one of the previous abstracts, don't miss its context in the next one and don't forget to add them in cited_in array.
Don't use internet.
Don't hallucinate."""

    # System instructions to extract and summarize diseases and physiological conditions information from the given json data
    CONDITIONS_EXTRACTION = """You are an extraction bot specifically designed for exact [disease,physiological condition]s extraction from massive of abstracts of scientific papers.
You are provided with abstracts in a json format:
[
  {
    "id": "001",
    "abstract": "<Here is the abstract of the first paper>"
  },...
]
Your task is to extract EVERY [disease,physiological condition] name from EVERY abstract.
Your output format is a json file with a given structure:
{
    "name": "<example condition name>",
    "context": "<short observations/facts as a context for the [disease,physiological condition] name>",
    "cited_in": [
      "001", "002"
    ]
}
Entities "gene_name" MUST! be unique, so if the [disease,physiological condition] name presented more than in one paper you must aggregate context information around the [disease,physiological condition] from all abstracts, formulate it like a short observations/facts. Aggregated descriptions should be at most 3 sentences long. Add paper id where [disease,physiological condition] was mentioned into 'cited_in' array.
Don't miss [disease,physiological condition]s in abstracts.
If [disease,physiological condition] name was already extracted from one of the previous abstracts, don't miss its context in the next one and don't forget to add them in cited_in array.
Don't use internet.
Don't hallucinate."""

    # System instructions to extract and summarize proteins information from the given json data
    PROTEINS_EXTRACTION = """You are an extraction bot specifically designed for exact [protein]s extraction from massive of abstracts of scientific papers.
You are provided with abstracts in a json format:
[
  {
    "id": "001",
    "abstract": "<Here is the abstract of the first paper>"
  },...
]
Your task is to extract EVERY [protein] name from EVERY abstract.
Your output format is a json file with a given structure:
{
    "name": "<example protein name>",
    "context": "<short observations/facts as a context for the [protein] name>",
    "cited_in": [
      "001", "002"
    ]
}
Entities "gene_name" MUST! be unique, so if the [protein] name presented more than in one paper you must aggregate context information around the [protein] from all abstracts, formulate it like a short observations/facts. Aggregated descriptions should be at most 3 sentences long. Add paper id where [protein] was mentioned into 'cited_in' array.
Don't miss [protein]s in abstracts.
If [protein] name was already extracted from one of the previous abstracts, don't miss its context in the next one and don't forget to add them in cited_in array.
Don't use internet.
Don't hallucinate."""

@functions_framework.http
def extract_genes(request: Request):
    try:
        # 1. Get si_mode from URL query or header
        si_mode = request.args.get("si_mode") or request.headers.get("x-si-mode")

        # 2. Resolve system prompt
        if not si_mode:
            return jsonify({
                "error": "Missing required parameter 'si_mode' (in query or header)"
            }), 400

        si_mode = si_mode.upper()

        try:
            system_prompt = SystemPrompt[si_mode].value
        except KeyError:
            return jsonify({
                "error": f"Invalid si_mode '{si_mode}'. Allowed values: {[e.name for e in SystemPrompt]}"
            }), 400

        # 3. Load abstracts from request body
        input_json = request.get_json(silent=True)
        if not input_json:
            return jsonify({"error": "Missing or invalid JSON body"}), 400

        abstracts_json = json.dumps(input_json)

        # 4. Generate content from model
        client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location="europe-west4",
        )

        model = "gemini-2.0-flash-001"
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=abstracts_json)]
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature = 0.25,
            top_p = 0.95,
            max_output_tokens = 8192,
            response_modalities = ["TEXT"],
            safety_settings = [types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF"
            ),types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"
            ),types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"
            ),types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
            )],
            system_instruction=[types.Part.from_text(text=system_prompt)],
        )

        response = client.models.generate_content(
            model = model,
            contents = contents,
            config = generate_content_config,
        )

        output_text = response.text.strip()
        if output_text.startswith("```json"):
            cleaned_json_str = output_text.removeprefix("```json").removesuffix("```").strip()
        elif output_text.startswith("json```"):
            cleaned_json_str = output_text.removeprefix("json```").removesuffix("```").strip()
        else:
            cleaned_json_str = output_text.strip('`').strip()

        parsed_data = json.loads(cleaned_json_str)

        return jsonify(parsed_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
