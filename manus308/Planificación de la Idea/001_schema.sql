-- ============================================================================
-- MMI — Motor RAG Industrial
-- Fase 0 · DDL de Postgres (Supabase) con Row Level Security
-- Fuente de verdad: documentos, versionado, activos, chunks (metadatos), chat.
-- Los vectores viven en Qdrant Cloud; aquí solo se guarda qdrant_point_id.
-- ============================================================================

-- Extensiones necesarias
create extension if not exists "pgcrypto";   -- gen_random_uuid()
create extension if not exists "uuid-ossp";

-- ----------------------------------------------------------------------------
-- 1. TENANTS (clientes / faenas)
-- ----------------------------------------------------------------------------
create table if not exists tenants (
    id          uuid primary key default gen_random_uuid(),
    slug        text not null unique,           -- p.ej. 'monitoring', 'faena-norte'
    nombre      text not null,
    created_at  timestamptz not null default now()
);

-- ----------------------------------------------------------------------------
-- 2. USERS (perfil de aplicación; referencia auth.users de Supabase)
-- ----------------------------------------------------------------------------
create table if not exists app_users (
    id          uuid primary key references auth.users (id) on delete cascade,
    tenant_id   uuid not null references tenants (id) on delete cascade,
    rol         text not null default 'lector'
                check (rol in ('admin', 'editor', 'aprobador', 'lector')),
    created_at  timestamptz not null default now()
);
create index if not exists app_users_tenant_idx on app_users (tenant_id);

-- ----------------------------------------------------------------------------
-- 3. ASSETS (activos / equipos a los que se refiere la documentación)
-- ----------------------------------------------------------------------------
create table if not exists assets (
    id          uuid primary key default gen_random_uuid(),
    tenant_id   uuid not null references tenants (id) on delete cascade,
    asset_code  text not null,                  -- p.ej. 'CH-430', 'BOM-210'
    descripcion text,
    criticidad  text check (criticidad in ('A', 'B', 'C')),
    created_at  timestamptz not null default now(),
    unique (tenant_id, asset_code)
);
create index if not exists assets_tenant_idx on assets (tenant_id);

-- ----------------------------------------------------------------------------
-- 4. DOCUMENTS (cabecera lógica de cada documento)
--    file_hash NO es unique global: el versionado lógico exige varias filas
--    por archivo (una por versión). La unicidad es (tenant_id, file_hash).
-- ----------------------------------------------------------------------------
create table if not exists documents (
    id               uuid primary key default gen_random_uuid(),
    tenant_id        uuid not null references tenants (id) on delete cascade,
    source_file_id   text,                      -- id/ruta del binario en Storage
    titulo           text not null,
    tipo             text not null              -- norma, guia, sop, manual_oem, tabla, presentacion
                     check (tipo in ('norma','guia','sop','manual_oem','tabla','presentacion','otro')),
    dominio          text,                      -- p.ej. 'mantenibilidad', 'confiabilidad'
    file_hash        text not null,             -- SHA-256 del binario
    version_label    text,                      -- p.ej. 'Rev 5', 'Rev 6', 'REV02'
    is_current       boolean not null default true,
    supersedes_id    uuid references documents (id),  -- versión que reemplaza
    extraction_method text not null default 'native'
                     check (extraction_method in ('native','ocr','tabular','slide')),
    created_at       timestamptz not null default now(),
    unique (tenant_id, file_hash)
);
create index if not exists documents_tenant_current_idx on documents (tenant_id, is_current);
create index if not exists documents_supersedes_idx on documents (supersedes_id);

-- ----------------------------------------------------------------------------
-- 5. CHUNKS (segmentos de texto con metadatos; el embedding vive en Qdrant)
-- ----------------------------------------------------------------------------
create table if not exists chunks (
    id              uuid primary key default gen_random_uuid(),
    tenant_id       uuid not null references tenants (id) on delete cascade,
    document_id     uuid not null references documents (id) on delete cascade,
    chunk_index     int not null,               -- orden dentro del documento
    content         text not null,
    token_count     int,
    page_start      int,
    page_end        int,
    section_path    text,                       -- p.ej. 'Cap 3 > 3.2 Alcance'
    criticality_level text not null default 'normal'
                    check (criticality_level in ('baja','normal','alta','seguridad')),
    asset_codes     text[] default '{}',        -- códigos de activo mencionados
    qdrant_point_id text,                       -- id del punto en Qdrant Cloud
    created_at      timestamptz not null default now(),
    unique (document_id, chunk_index)
);
create index if not exists chunks_tenant_idx on chunks (tenant_id);
create index if not exists chunks_document_idx on chunks (document_id);
create index if not exists chunks_criticality_idx on chunks (criticality_level);
create index if not exists chunks_asset_codes_gin on chunks using gin (asset_codes);
create index if not exists chunks_qdrant_point_idx on chunks (qdrant_point_id);

-- tsvector generado para búsqueda léxica de respaldo (español)
alter table chunks
    add column if not exists content_tsv tsvector
    generated always as (to_tsvector('spanish', content)) stored;
create index if not exists chunks_content_tsv_gin on chunks using gin (content_tsv);

-- ----------------------------------------------------------------------------
-- 6. CHAT_SESSIONS / CHAT_MESSAGES (trazabilidad de consultas y CoVe)
-- ----------------------------------------------------------------------------
create table if not exists chat_sessions (
    id          uuid primary key default gen_random_uuid(),
    tenant_id   uuid not null references tenants (id) on delete cascade,
    user_id     uuid not null references app_users (id) on delete cascade,
    titulo      text,
    created_at  timestamptz not null default now()
);
create index if not exists chat_sessions_tenant_idx on chat_sessions (tenant_id);

create table if not exists chat_messages (
    id              uuid primary key default gen_random_uuid(),
    session_id      uuid not null references chat_sessions (id) on delete cascade,
    tenant_id       uuid not null references tenants (id) on delete cascade,
    role            text not null check (role in ('user','assistant','system')),
    content         text not null,
    evidence_label  text check (evidence_label in ('supported','partial','not_found','conflict')),
    citations       jsonb default '[]',         -- [{chunk_id, document_id, page, quote}]
    cove_status     text default 'pendiente'
                    check (cove_status in ('pendiente','aprobado','rechazado','corregido')),
    cove_reviewer   uuid references app_users (id),
    cove_reviewed_at timestamptz,
    created_at      timestamptz not null default now()
);
create index if not exists chat_messages_session_idx on chat_messages (session_id);
create index if not exists chat_messages_tenant_idx on chat_messages (tenant_id);
create index if not exists chat_messages_cove_idx on chat_messages (cove_status);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

-- Helper: tenant del usuario autenticado (evita recursión en políticas)
create or replace function current_tenant_id()
returns uuid
language sql stable
security definer
set search_path = public
as $$
    select tenant_id from app_users where id = auth.uid()
$$;

-- Activar RLS en todas las tablas de datos
alter table tenants        enable row level security;
alter table app_users      enable row level security;
alter table assets         enable row level security;
alter table documents      enable row level security;
alter table chunks         enable row level security;
alter table chat_sessions  enable row level security;
alter table chat_messages  enable row level security;

-- Políticas: cada usuario solo ve/opera filas de su propio tenant.
-- Se crean de forma idempotente (drop previo si existen).

-- TENANTS: un usuario ve solo su tenant
drop policy if exists tenants_isolation on tenants;
create policy tenants_isolation on tenants
    using (id = current_tenant_id())
    with check (id = current_tenant_id());

-- APP_USERS: un usuario ve solo usuarios de su tenant
drop policy if exists app_users_isolation on app_users;
create policy app_users_isolation on app_users
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

-- ASSETS
drop policy if exists assets_isolation on assets;
create policy assets_isolation on assets
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

-- DOCUMENTS
drop policy if exists documents_isolation on documents;
create policy documents_isolation on documents
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

-- CHUNKS
drop policy if exists chunks_isolation on chunks;
create policy chunks_isolation on chunks
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

-- CHAT_SESSIONS
drop policy if exists chat_sessions_isolation on chat_sessions;
create policy chat_sessions_isolation on chat_sessions
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

-- CHAT_MESSAGES
drop policy if exists chat_messages_isolation on chat_messages;
create policy chat_messages_isolation on chat_messages
    using (tenant_id = current_tenant_id())
    with check (tenant_id = current_tenant_id());

-- ============================================================================
-- Datos semilla mínimos (un tenant de arranque para pruebas de RLS)
-- ============================================================================
insert into tenants (slug, nombre)
values ('monitoring', 'Monitoring SpA')
on conflict (slug) do nothing;

-- ============================================================================
-- Fin del DDL
-- ============================================================================
