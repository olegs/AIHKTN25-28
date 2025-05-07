-- Create the embedding model if it does not exist
CREATE MODEL IF NOT EXISTS `aihktn25-28.dataset_eu_test.embedding_model002`
  REMOTE WITH CONNECTION `projects/aihktn25-28/locations/eu/connections/eu_general`
  OPTIONS (
    ENDPOINT = 'text-multilingual-embedding-002'
  );

-- Create the embeddings table if it does not exist
-- NOTE: This operation may be time-consuming (~50 minutes)
CREATE TABLE IF NOT EXISTS `dataset_eu_test.embeddings_table` AS
SELECT *
FROM ML.GENERATE_EMBEDDING(
  MODEL `aihktn25-28.dataset_eu_test.embedding_model002`,
  (
    SELECT 
      id, 
      abstract AS content
    FROM `aihktn25-28.dataset_eu_test.2023_with_first_row`
    WHERE abstract IS NOT NULL
  )
);

-- Create or replace a table for the input query to be embedded
-- This table is used as input to the vector search (mocked with a hardcoded string for now)
CREATE OR REPLACE TABLE `dataset_eu_test.embeddings_query` AS
SELECT *
FROM ML.GENERATE_EMBEDDING(
  MODEL `aihktn25-28.dataset_eu_test.embedding_model002`,
  (
    SELECT 'Migracja nerwowych komórek macierzystych zależy od osi w SM.' AS content
  )
);

-- Create or replace the vector index on the embeddings table
CREATE OR REPLACE VECTOR INDEX my_embedding_index
ON `dataset_eu_test.embeddings_table` (ml_generate_embedding_result)
OPTIONS (
  distance_type = 'COSINE',
  index_type = 'IVF'
);

-- Perform the vector search and return top 1000 results ordered by similarity
SELECT base.id
FROM VECTOR_SEARCH(
  TABLE `dataset_eu_test.embeddings_table`, 'ml_generate_embedding_result',
  TABLE `dataset_eu_test.embeddings_query`, 'ml_generate_embedding_result',
  top_k => 1000,
  distance_type => 'COSINE'
)
ORDER BY distance ASC;
