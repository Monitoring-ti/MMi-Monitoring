-- MMI — Ingesta v2: catálogo lógico, estados de versión, jobs, metadatos de chunk
-- Ejecutar en Supabase SQL Editor después de 001_schema.sql

-- Catálogo lógico (identidad del documento, no del archivo)
create table if not exists document_catalog (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    document_key    text not null,
    titulo          text not null,
    tipo            text not null,
    dominio         text,
    origen          text default 'local',
    created_at      timestamptz not null default now(),
    unique (tenant_id, document_key)
);
create index if not exists document_catalog_tenant_idx on document_catalog (tenant_id);

-- Extender documents como versión física
alter table documents add column if not exists catalog_id uuid references document_catalog (id);
alter table documents add column if not exists document_key text;
alter table documents add column if not exists content_hash text;
alter table documents add column if not exists status text not null default 'received'
    check (status in ('received','processing','indexed','active','failed','superseded'));
alter table documents add column if not exists error_message text;
alter table documents add column if not exists activated_at timestamptz;

create index if not exists documents_catalog_idx on documents (catalog_id);
create index if not exists documents_status_idx on documents (tenant_id, status);
create index if not exists documents_key_idx on documents (tenant_id, document_key);

-- Jobs de ingesta
create table if not exists ingestion_jobs (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    document_id     uuid references documents (id) on delete set null,
    catalog_id      uuid references document_catalog (id) on delete set null,
    stage           text not null,
    status          text not null default 'running'
        check (status in ('running','completed','failed','skipped')),
    attempt         int not null default 1,
    metrics         jsonb default '{}',
    error_message   text,
    started_at      timestamptz not null default now(),
    finished_at     timestamptz
);
create index if not exists ingestion_jobs_tenant_idx on ingestion_jobs (tenant_id);
create index if not exists ingestion_jobs_document_idx on ingestion_jobs (document_id);

-- Metadatos extendidos por chunk (opcional; vigencia heredada de versión)
create table if not exists chunk_metadata (
    id              uuid primary key default gen_random_uuid(),
    chunk_id        uuid not null references chunks (id) on delete cascade,
    tenant_id       uuid not null references tenants (id) on delete cascade,
    asset_tag       text,
    modulo          text,
    tipo_documental text,
    vigencia_desde  date,
    vigencia_hasta  date,
    extra           jsonb default '{}',
    unique (chunk_id)
);

-- Catálogo EAM/CMMS (stub)
create table if not exists catalog_assets (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    asset_tag       text not null,
    modulo          text,
    codigo_tecnico  text,
    vigente         boolean not null default true,
    unique (tenant_id, asset_tag)
);

alter table document_catalog enable row level security;
alter table ingestion_jobs enable row level security;
alter table chunk_metadata enable row level security;
alter table catalog_assets enable row level security;

drop policy if exists document_catalog_isolation on document_catalog;
create policy document_catalog_isolation on document_catalog
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

drop policy if exists ingestion_jobs_isolation on ingestion_jobs;
create policy ingestion_jobs_isolation on ingestion_jobs
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

drop policy if exists chunk_metadata_isolation on chunk_metadata;
create policy chunk_metadata_isolation on chunk_metadata
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

drop policy if exists catalog_assets_isolation on catalog_assets;
create policy catalog_assets_isolation on catalog_assets
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());
