-- MMI — DOCX v1: bloques jerárquicos, tablas e imágenes
-- Ejecutar en Supabase SQL Editor después de 002_ingestion_v2.sql
-- Especificación: docs/plan-docx-extraction.md

create table if not exists docx_documents (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    document_id     uuid not null references documents (id) on delete cascade,
    file_hash       text not null,
    docx_content_hash text,
    source_uri      text not null,
    engine          text not null default 'python-docx',
    engine_version  text,
    config          jsonb default '{}',
    block_count     int,
    blocks_pass     int,
    status          text not null default 'processing'
        check (status in ('processing','validated','failed','superseded')),
    created_at      timestamptz not null default now(),
    unique (document_id)
);
create index if not exists docx_documents_tenant_idx on docx_documents (tenant_id);
create index if not exists docx_documents_document_idx on docx_documents (document_id);

create table if not exists document_blocks (
    id                  uuid primary key default gen_random_uuid(),
    docx_document_id    uuid not null references docx_documents (id) on delete cascade,
    block_index         int not null,
    block_type          text not null
        check (block_type in (
            'heading','paragraph','list','table','image',
            'footnote','reference','comment','other'
        )),
    level               int,
    section_path        text,
    page_or_position    int,
    text_raw            text not null default '',
    text_normalized     text,
    block_content_hash  text,
    extraction_quality  text not null default 'pass'
        check (extraction_quality in ('pass','review','reject')),
    markdown            text,
    media_ref           text,
    extra               jsonb default '{}',
    unique (docx_document_id, block_index)
);
create index if not exists document_blocks_doc_idx on document_blocks (docx_document_id);
create index if not exists document_blocks_type_idx on document_blocks (docx_document_id, block_type);
create index if not exists document_blocks_section_idx on document_blocks (docx_document_id, section_path);

create table if not exists document_tables (
    id              uuid primary key default gen_random_uuid(),
    block_id        uuid not null references document_blocks (id) on delete cascade,
    headers         jsonb,
    rows            jsonb,
    row_count       int,
    col_count       int,
    markdown        text
);
create index if not exists document_tables_block_idx on document_tables (block_id);

create table if not exists document_media (
    id              uuid primary key default gen_random_uuid(),
    docx_document_id uuid not null references docx_documents (id) on delete cascade,
    block_id        uuid references document_blocks (id) on delete set null,
    media_ref       text not null,
    mime_type       text,
    width_px        int,
    height_px       int,
    storage_uri     text,
    ocr_text        text,
    ocr_confidence  real,
    extra           jsonb default '{}'
);
create index if not exists document_media_doc_idx on document_media (docx_document_id);
create index if not exists document_media_block_idx on document_media (block_id);

create table if not exists docx_validations (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    docx_document_id uuid references docx_documents (id) on delete cascade,
    block_id        uuid references document_blocks (id) on delete set null,
    rule            text not null,
    status          text not null
        check (status in ('pass','review','reject')),
    field_name      text,
    raw_value       text,
    normalized_value text,
    expected_value  text,
    diff            jsonb,
    reviewed_by     text,
    reviewed_at     timestamptz,
    created_at      timestamptz not null default now()
);
create index if not exists docx_validations_tenant_idx on docx_validations (tenant_id);
create index if not exists docx_validations_doc_idx on docx_validations (docx_document_id);

-- Enlazar chunks → bloque origen (opcional; complementa chunk_metadata.extra)
alter table chunk_metadata add column if not exists block_id uuid references document_blocks (id) on delete set null;
alter table chunk_metadata add column if not exists section_path text;

create index if not exists chunk_metadata_block_idx on chunk_metadata (block_id);

alter table docx_documents enable row level security;
alter table document_blocks enable row level security;
alter table document_tables enable row level security;
alter table document_media enable row level security;
alter table docx_validations enable row level security;

drop policy if exists docx_documents_isolation on docx_documents;
create policy docx_documents_isolation on docx_documents
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

drop policy if exists document_blocks_isolation on document_blocks;
create policy document_blocks_isolation on document_blocks
    using (docx_document_id in (
        select id from docx_documents where tenant_id = current_tenant_id()
    ));

drop policy if exists document_tables_isolation on document_tables;
create policy document_tables_isolation on document_tables
    using (block_id in (
        select b.id from document_blocks b
        join docx_documents d on d.id = b.docx_document_id
        where d.tenant_id = current_tenant_id()
    ));

drop policy if exists document_media_isolation on document_media;
create policy document_media_isolation on document_media
    using (docx_document_id in (
        select id from docx_documents where tenant_id = current_tenant_id()
    ));

drop policy if exists docx_validations_isolation on docx_validations;
create policy docx_validations_isolation on docx_validations
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());
