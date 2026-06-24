"""Add chunk_method field to documents table

This migration adds the chunk_method field to support multiple chunking strategies.

Run this SQL in your PostgreSQL database:
"""

ALTER TABLE documents ADD COLUMN IF NOT EXISTS chunk_method VARCHAR(50);

-- Update parse_status values
-- Old: pending, processing, done, failed
-- New: pending, parsing, parsed, chunking, done, failed

UPDATE documents SET parse_status = 'parsed' WHERE parse_status = 'processing';

COMMENT ON COLUMN documents.chunk_method IS 'Chunking method: intelligent, qa, table, general, parent_child, recursive';
COMMENT ON COLUMN documents.parse_status IS 'Status: pending, parsing, parsed, chunking, done, failed';
