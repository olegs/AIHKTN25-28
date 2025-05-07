import os

# TODO fix me!!!!
PUBTRENDS_API = os.getenv(
    "PUBTRENDS_API",
    ""
)

GOOGLE_SUMMARIZE_CATEGORIES_ENDPOINT = os.getenv(
    "GOOGLE_SUMMARIZE_CATEGORIES_ENDPOINT",
    ""
)


STEP_NOT_STARTED = 'not_started'
STEP_PENDING = 'pending'
STEP_COMPLETE = 'complete'
STEP_ERROR = 'error'

START_STEP = 'Starting analysis'
PUBTRENDS_STEP = 'Waiting for the PubTrends analysis results'
SUMMARIZE_STEP = 'Building summaries for categories'

SEMANTIC_SEARCH_STEP = 'Semantic search'

def create_text_steps():
    return {
        START_STEP: STEP_NOT_STARTED,
        PUBTRENDS_STEP: STEP_NOT_STARTED,
        SUMMARIZE_STEP: STEP_NOT_STARTED
    }

def create_semantic_steps():
    return {
        START_STEP: STEP_NOT_STARTED,
        SEMANTIC_SEARCH_STEP: STEP_NOT_STARTED,
        PUBTRENDS_STEP: STEP_NOT_STARTED,
        SUMMARIZE_STEP: STEP_NOT_STARTED
    }

