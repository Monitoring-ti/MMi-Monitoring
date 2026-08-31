-- MMI — OCR v1: capas con incertidumbre (crudo, normalizado, confianza, validación)
-- Ejecutar en Supabase SQL Editor después de 002_ingestion_v2.sql
-- Especificación: docs/plan-fase-c-ocr.md

create table if not exists ocr_documents (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    document_id     uuid not null references documents (id) on delete cascade,
    file_hash       text not null,
    ocr_content_hash text,
    source_uri      text not null,
    engine          text not null,
    engine_version  text,
    config          jsonb default '{}',
    language        text,
    orientation     text,
    status          text not null default 'processing'
        check (status in ('processing','validated','failed','superseded')),
    created_at      timestamptz not null default now(),
    unique (document_id)
);
create index if not exists ocr_documents_tenant_idx on ocr_documents (tenant_id);
create index if not exists ocr_documents_document_idx on ocr_documents (document_id);

create table if not exists ocr_pages (
    id              uuid primary key default gen_random_uuid(),
    ocr_document_id uuid not null references ocr_documents (id) on delete cascade,
    page_number     int not null,
    page_hash       text,
    original_uri    text,
    preprocessed_uri text,
    width_px        int,
    height_px       int,
    confidence      real,
    language        text,
    status          text not null default 'pending'
        check (status in ('pending','ocr_done','validated','failed','skipped')),
    metrics         jsonb default '{}',
    unique (ocr_document_id, page_number)
);
create index if not exists ocr_pages_doc_idx on ocr_pages (ocr_document_id);

create table if not exists ocr_blocks (
    id              uuid primary key default gen_random_uuid(),
    ocr_page_id     uuid not null references ocr_pages (id) on delete cascade,
    block_index     int not null,
    block_type      text not null,
    text_raw        text not null,
    text_normalized text,
    bbox            jsonb,
    confidence      real,
    language        text,
    extra           jsonb default '{}'
);
create index if not exists ocr_blocks_page_idx on ocr_blocks (ocr_page_id);

create table if not exists ocr_tokens (
    id              uuid primary key default gen_random_uuid(),
    ocr_block_id    uuid not null references ocr_blocks (id) on delete cascade,
    token_index     int not null,
    text            text not null,
    confidence      real,
    bbox            jsonb
);
create index if not exists ocr_tokens_block_idx on ocr_tokens (ocr_block_id);

create table if not exists ocr_tables (
    id              uuid primary key default gen_random_uuid(),
    ocr_block_id    uuid not null references ocr_blocks (id) on delete cascade,
    headers         jsonb,
    rows            jsonb,
    cell_confidence jsonb,
    markdown        text
);

create table if not exists ocr_validations (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    ocr_document_id uuid references ocr_documents (id) on delete cascade,
    ocr_page_id     uuid references ocr_pages (id) on delete set null,
    ocr_block_id    uuid references ocr_blocks (id) on delete set null,
    rule            text not null,
    status          text not null
        check (status in ('pass','review','reject')),
    field_name      text,
    raw_value       text,
    normalized_value text,
    expected_value  text,
    confidence      real,
    diff            jsonb,
    reviewed_by     text,
    reviewed_at     timestamptz,
    created_at      timestamptz not null default now()
);
create index if not exists ocr_validations_tenant_idx on ocr_validations (tenant_id);
create index if not exists ocr_validations_doc_idx on ocr_validations (ocr_document_id);

create table if not exists ocr_jobs (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    ocr_document_id uuid references ocr_documents (id) on delete set null,
    document_id     uuid references documents (id) on delete set null,
    stage           text not null,
    status          text not null default 'running'
        check (status in ('running','completed','failed','skipped')),
    attempt         int not null default 1,
    last_page       int,
    metrics         jsonb default '{}',
    error_message   text,
    started_at      timestamptz not null default now(),
    finished_at     timestamptz
);
create index if not exists ocr_jobs_tenant_idx on ocr_jobs (tenant_id);
create index if not exists ocr_jobs_document_idx on ocr_jobs (document_id);

alter table ocr_documents enable row level security;
alter table ocr_pages enable row level security;
alter table ocr_blocks enable row level security;
alter table ocr_tokens enable row level security;
alter table ocr_tables enable row level security;
alter table ocr_validations enable row level security;
alter table ocr_jobs enable row level security;

drop policy if exists ocr_documents_isolation on ocr_documents;
create policy ocr_documents_isolation on ocr_documents
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

drop policy if exists ocr_pages_isolation on ocr_pages;
create policy ocr_pages_isolation on ocr_pages
    using (ocr_document_id in (
        select id from ocr_documents where tenant_id = current_tenant_id()
    ));

drop policy if exists ocr_blocks_isolation on ocr_blocks;
create policy ocr_blocks_isolation on ocr_blocks
    using (ocr_page_id in (
        select p.id from ocr_pages p
        join ocr_documents d on d.id = p.ocr_document_id
        where d.tenant_id = current_tenant_id()
    ));

drop policy if exists ocr_tokens_isolation on ocr_tokens;
create policy ocr_tokens_isolation on ocr_tokens
    using (ocr_block_id in (
        select b.id from ocr_blocks b
        join ocr_pages p on p.id = b.ocr_page_id
        join ocr_documents d on d.id = p.ocr_document_id
        where d.tenant_id = current_tenant_id()
    ));

drop policy if exists ocr_tables_isolation on ocr_tables;
create policy ocr_tables_isolation on ocr_tables
    using (ocr_block_id in (
        select b.id from ocr_blocks b
        join ocr_pages p on p.id = b.ocr_page_id
        join ocr_documents d on d.id = p.ocr_document_id
        where d.tenant_id = current_tenant_id()
    ));

drop policy if exists ocr_validations_isolation on ocr_validations;
create policy ocr_validations_isolation on ocr_validations
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

drop policy if exists ocr_jobs_isolation on ocr_jobs;
create policy ocr_jobs_isolation on ocr_jobs
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());
