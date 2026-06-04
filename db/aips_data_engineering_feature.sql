CREATE TABLE IF NOT EXISTS public.aips_data_engineering_feature (
    data_feature_id BIGSERIAL PRIMARY KEY,
    feature_time TIMESTAMP DEFAULT NOW(),
    feature_category VARCHAR(80),
    source_table VARCHAR(120),
    source_pk VARCHAR(120),
    cnc_machine_id VARCHAR(80),
    work_order_no VARCHAR(80),
    material_no VARCHAR(80),
    feature_name VARCHAR(120),
    raw_value TEXT,
    cleaned_value TEXT,
    normalized_value NUMERIC(12,6),
    time_bucket VARCHAR(80),
    feature_vector_json JSONB,
    engineering_step VARCHAR(80) DEFAULT 'FEATURE_ENGINEERING',
    downstream_stage VARCHAR(120),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_aips_data_engineering_feature_category
    ON public.aips_data_engineering_feature(feature_category);

CREATE INDEX IF NOT EXISTS ix_aips_data_engineering_feature_downstream
    ON public.aips_data_engineering_feature(downstream_stage);

CREATE INDEX IF NOT EXISTS ix_aips_data_engineering_feature_cnc
    ON public.aips_data_engineering_feature(cnc_machine_id);
