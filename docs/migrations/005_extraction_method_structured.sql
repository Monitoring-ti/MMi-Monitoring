-- Opcional: permitir extraction_method = structured para DOCX (B7)
-- Sin esto, DOCX usa 'native' en EXT_METHOD (compatible con 001_schema.sql)

alter table documents drop constraint if exists documents_extraction_method_check;
alter table documents add constraint documents_extraction_method_check
    check (extraction_method in ('native','ocr','tabular','slide','structured'));
