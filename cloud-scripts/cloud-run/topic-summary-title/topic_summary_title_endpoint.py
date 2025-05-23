# Google Cloud Function Impl
#   [Purpose]
#       Generates title for the topic summary generated by `topic_summarization_endpoint.py`
#       function. Implementation force Gemini prompt to make title from most frequent
#       keywords observed in whole topic abstracts list, not just using only summary text.

import functions_framework
import json
from flask import Request, jsonify
from google import genai
from google.genai import types

import os

# XXX: Configure through env variables!
VERTEX_CLIENT_PROJECT = os.environ.get('GCP_PROJECT') or 'my_project'


SYSTEM_INSTRUCTIONS_LLM_PROMPT_SUMMARY_TITLE = """
You are a research bot, tasked with helping scientific researchers to assign a title to scientific text about some topic using text submitted to you and submitted keywords. Your job is to summarize the scientific topic text into one sentence to you using suggested keywords.

Be sure to:
* make a representative and short title for the given text
* focus on the main points of the text
* keep it condense and to the point
* NEVER output more that one sentence
* do not hallucinate
<EXCEPTION>
do not put by NO MEANS more that one sentence. Do not highlight title as bold string. E.g not like below:
**Virally Infected Diseases and Vaccine Strategies in Virology**

This research discusses respiratory infections, including COVID-19, and HPV-associated diseases. The emergence of SARS-CoV-2 led to a global pandemic, with vaccines showing efficacy. Community-acquired pneumonia and other respiratory viruses are also discussed. HPV infection is
</EXCEPTION>
"""

@functions_framework.http
def assign_title(request: Request):
    try:
        topic_summary_data = request.get_json(silent=True)
        # topic_summary_data_raw = topic_summary_data
        if not topic_summary_data:
            return jsonify({"error": "Missing or invalid JSON body"}), 400

        # If it's still a string (e.g. '{"a": 1, "b": 2}' as a str)
        if isinstance(topic_summary_data, str):
            try:
                topic_summary_data = json.loads(topic_summary_data)
            except json.JSONDecodeError:
                return jsonify({"error": "Cannot parse JSON body"}), 400

        if ('summary' not in topic_summary_data) or ('topics_keywords' not in topic_summary_data):
            return jsonify({
                "error": "Missing required keys 'summary' or 'topics_keywords' in JSON body"
                # "error": f"Missing required keys 'summary' or 'topics_keywords' in JSON body. Raw data type: {type(topic_summary_data_raw)}, Parsed data type: {type(topic_summary_data)}  Keys: {','.join(list(topic_data.keys()))}"
            }), 400

        # TODO: validate input, e.g. size, truncate if necessary
        output_text = do_llm_prompt_assign_title_to_summary(topic_summary_data['summary'], topic_summary_data['topics_keywords'])

        return jsonify({
            'title': output_text,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def do_llm_prompt_assign_title_to_summary(summary, topics_keywords):
    args = dict(
        model="gemini-2.0-flash-lite-001",
        temperature = 0.01, top_p = 0.95, top_k=None, max_output_tokens = 64,
    )

    topic_desc = ",".join(topics_keywords)
    llm_response = llm_generate(
        project=VERTEX_CLIENT_PROJECT,
        system_instructions=SYSTEM_INSTRUCTIONS_LLM_PROMPT_SUMMARY_TITLE,
        text_to_summarize=f"KEYWORDS: {topic_desc}\nTEXT:\n{summary}",
        **args
    )

    #print(llm_response)
    print("[DONE] Response len", len(llm_response))

    return llm_response


def llm_generate(
        *,
        project,
        system_instructions,
        text_to_summarize,
        model, temperature, top_p, top_k, max_output_tokens,
        thinking_budget=None,
        max_retries=5
):
    # print(text_to_summarize)
    # if True:
    #     return ""

    client = genai.Client(
        vertexai=True,
        project=project,
        location="us-central1",
    )

    msg1_text1 = types.Part.from_text(text=text_to_summarize)
    si_text1 = system_instructions

    contents = [types.Content(role="user", parts=[msg1_text1])]

    optional_args = {}
    if thinking_budget is not None:
        optional_args['thinking_config'] = types.ThinkingConfig(thinking_budget=thinking_budget)

    generate_content_config = types.GenerateContentConfig(
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        seed=0,
        max_output_tokens=max_output_tokens,
        response_modalities=["TEXT"],
        safety_settings=[types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="OFF"
        ), types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="OFF"
        ), types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="OFF"
        ), types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="OFF"
        )],
        system_instruction=[types.Part.from_text(text=si_text1)],
        **optional_args
    )

    retries_cnt = 0
    while retries_cnt < max_retries:
        chunks = []
        retries_cnt += 1

        for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
        ):
            assert chunk is not None
            if chunk.text is None:
                # when chunk.text is None - smth goes wrong - XXX: is know bug in 2.5 ==> REDO
                chunks = None
                break

            # if debug:
            #     print("CHUNK: [", chunk.text, end="]\n")

            if chunk.text is not None:
                chunks.append(chunk.text)

        # join chunks:
        if chunks is None:
            print(f"Retry #{retries_cnt}...")
            continue

        return "".join(chunks)

    raise Exception("Cannot summarize text. Maximum number of retries reached")
