-- public.aips_business_service_log definition

-- Drop table

-- DROP TABLE public.aips_business_service_log;

CREATE TABLE public.aips_business_service_log (
	service_log_id bigserial NOT NULL,
	service_time timestamp DEFAULT now() NULL,
	service_name varchar(120) NULL,
	operation_name varchar(120) NULL,
	operator_id varchar(80) NULL,
	request_json jsonb NULL,
	result_status varchar(40) NULL,
	result_message text NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_business_service_log_pkey PRIMARY KEY (service_log_id)
);


-- public.aips_cnc_daily_schedule_result definition

-- Drop table

-- DROP TABLE public.aips_cnc_daily_schedule_result;

CREATE TABLE public.aips_cnc_daily_schedule_result (
	schedule_id bigserial NOT NULL,
	schedule_date date NULL,
	work_order_no varchar(80) NULL,
	product_no varchar(80) NULL,
	product_name varchar(120) NULL,
	step_no int4 NULL,
	step_name varchar(120) NULL,
	cnc_machine_id varchar(80) NULL,
	sequence_no_on_cnc int4 NULL,
	planned_qty numeric(14, 4) NULL,
	processing_minutes int4 NULL,
	setup_minutes int4 DEFAULT 0 NULL,
	total_minutes int4 NULL,
	start_minute int4 NULL,
	end_minute int4 NULL,
	start_time timestamp NULL,
	end_time timestamp NULL,
	schedule_status varchar(40) DEFAULT 'SCHEDULED'::character varying NULL,
	schedule_reason text NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_cnc_daily_schedule_result_pkey PRIMARY KEY (schedule_id)
);
CREATE INDEX ix_cnc_daily_schedule_cnc ON public.aips_cnc_daily_schedule_result USING btree (cnc_machine_id, schedule_date);
CREATE INDEX ix_cnc_daily_schedule_date ON public.aips_cnc_daily_schedule_result USING btree (schedule_date);


-- public.aips_dashboard_widget definition

-- Drop table

-- DROP TABLE public.aips_dashboard_widget;

CREATE TABLE public.aips_dashboard_widget (
	widget_id bigserial NOT NULL,
	widget_code varchar(80) NULL,
	widget_name varchar(120) NULL,
	widget_type varchar(80) NULL,
	data_source varchar(120) NULL,
	refresh_seconds int4 DEFAULT 30 NULL,
	enabled_flag bool DEFAULT true NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_dashboard_widget_pkey PRIMARY KEY (widget_id)
);


-- public.aips_data_engineering_feature definition

-- Drop table

-- DROP TABLE public.aips_data_engineering_feature;

CREATE TABLE public.aips_data_engineering_feature (
	data_feature_id bigserial NOT NULL,
	feature_time timestamp DEFAULT now() NULL,
	feature_category varchar(80) NULL,
	source_table varchar(120) NULL,
	source_pk varchar(120) NULL,
	cnc_machine_id varchar(80) NULL,
	work_order_no varchar(80) NULL,
	material_no varchar(80) NULL,
	feature_name varchar(120) NULL,
	raw_value text NULL,
	cleaned_value text NULL,
	normalized_value numeric(12, 6) NULL,
	time_bucket varchar(80) NULL,
	feature_vector_json jsonb NULL,
	engineering_step varchar(80) DEFAULT 'FEATURE_ENGINEERING'::character varying NULL,
	downstream_stage varchar(120) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_data_engineering_feature_pkey PRIMARY KEY (data_feature_id)
);
CREATE INDEX ix_aips_data_engineering_feature_category ON public.aips_data_engineering_feature USING btree (feature_category);
CREATE INDEX ix_aips_data_engineering_feature_cnc ON public.aips_data_engineering_feature USING btree (cnc_machine_id);
CREATE INDEX ix_aips_data_engineering_feature_downstream ON public.aips_data_engineering_feature USING btree (downstream_stage);


-- public.aips_data_sync_log definition

-- Drop table

-- DROP TABLE public.aips_data_sync_log;

CREATE TABLE public.aips_data_sync_log (
	sync_id bigserial NOT NULL,
	sync_time timestamp DEFAULT now() NULL,
	source_system varchar(80) NULL,
	target_table varchar(120) NULL,
	sync_type varchar(80) NULL,
	sync_status varchar(40) NULL,
	record_count int4 DEFAULT 0 NULL,
	message text NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_data_sync_log_pkey PRIMARY KEY (sync_id)
);


-- public.aips_dqn_action_log definition

-- Drop table

-- DROP TABLE public.aips_dqn_action_log;

CREATE TABLE public.aips_dqn_action_log (
	action_id bigserial NOT NULL,
	state_id int8 NULL,
	action_time timestamp DEFAULT now() NULL,
	action_type varchar(80) NULL,
	action_name varchar(120) NULL,
	work_order_no varchar(80) NULL,
	product_no varchar(80) NULL,
	original_cnc_machine_id varchar(80) NULL,
	suggested_cnc_machine_id varchar(80) NULL,
	original_start_time timestamp NULL,
	suggested_start_time timestamp NULL,
	original_finish_time timestamp NULL,
	suggested_finish_time timestamp NULL,
	replenishment_required_flag bool DEFAULT false NULL,
	maintenance_check_required_flag bool DEFAULT false NULL,
	expected_delay_reduction_hours numeric(12, 4) NULL,
	expected_oee_improvement_rate numeric(8, 4) NULL,
	expected_shortage_risk_reduction numeric(8, 4) NULL,
	action_confidence_score numeric(8, 4) NULL,
	action_status varchar(40) DEFAULT 'PENDING'::character varying NULL,
	action_reason text NULL,
	created_at timestamp DEFAULT now() NULL,
	shortage_priority_decision_id int8 NULL,
	customer_shortage_risk_score numeric(10, 4) NULL,
	shortage_priority_q_value numeric(14, 4) NULL,
	shortage_priority_reason text NULL,
	CONSTRAINT aips_dqn_action_log_pkey PRIMARY KEY (action_id)
);


-- public.aips_electric_alert_setting definition

-- Drop table

-- DROP TABLE public.aips_electric_alert_setting;

CREATE TABLE public.aips_electric_alert_setting (
	alert_setting_id bigserial NOT NULL,
	device_type varchar(40) DEFAULT '2'::character varying NULL,
	alert_type varchar(40) NULL,
	alert_desc varchar(200) NULL,
	thrd_value numeric(12, 4) NULL,
	thrd_value2 numeric(12, 4) NULL,
	enabled_flag bool DEFAULT true NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_electric_alert_setting_pkey PRIMARY KEY (alert_setting_id)
);


-- public.aips_electric_cnc_link definition

-- Drop table

-- DROP TABLE public.aips_electric_cnc_link;

CREATE TABLE public.aips_electric_cnc_link (
	link_id bigserial NOT NULL,
	cnc_machine_id varchar(80) NULL,
	meter_id varchar(80) NULL,
	device_ip varchar(80) NULL,
	protocol_type varchar(80) DEFAULT 'MODBUS_TCP'::character varying NULL,
	modbus_unit_id int4 NULL,
	source_spec varchar(80) DEFAULT 'FFA_ELECTRIC_MONITOR'::character varying NULL,
	connected_flag bool DEFAULT true NULL,
	last_collect_time timestamp NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_electric_cnc_link_pkey PRIMARY KEY (link_id)
);


-- public.aips_electric_dashboard_snapshot definition

-- Drop table

-- DROP TABLE public.aips_electric_dashboard_snapshot;

CREATE TABLE public.aips_electric_dashboard_snapshot (
	snapshot_id bigserial NOT NULL,
	snapshot_time timestamp DEFAULT now() NULL,
	cnc_machine_id varchar(80) NULL,
	meter_id varchar(80) NULL,
	monthly_ae numeric(14, 4) NULL,
	last_year_monthly_ae numeric(14, 4) NULL,
	carbon_emission numeric(14, 4) NULL,
	last_year_carbon_emission numeric(14, 4) NULL,
	max_demand_kw numeric(12, 4) NULL,
	max_power_kw numeric(12, 4) NULL,
	avg_power_factor numeric(8, 4) NULL,
	uunbl numeric(8, 4) NULL,
	lunbl numeric(8, 4) NULL,
	load_factor numeric(8, 4) NULL,
	source_system varchar(80) DEFAULT 'AIPS'::character varying NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_electric_dashboard_snapshot_pkey PRIMARY KEY (snapshot_id)
);


-- public.aips_exception_event definition

-- Drop table

-- DROP TABLE public.aips_exception_event;

CREATE TABLE public.aips_exception_event (
	event_id bigserial NOT NULL,
	event_time timestamp DEFAULT now() NULL,
	event_type varchar(80) NULL,
	event_level varchar(40) NULL,
	cnc_machine_id varchar(80) NULL,
	work_order_no varchar(80) NULL,
	material_no varchar(80) NULL,
	event_description text NULL,
	detected_by varchar(120) NULL,
	shortage_qty numeric(14, 4) NULL,
	impact_on_schedule_flag bool DEFAULT false NULL,
	impact_hours numeric(12, 4) NULL,
	handled_flag bool DEFAULT false NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_exception_event_pkey PRIMARY KEY (event_id)
);


-- public.aips_external_integration_log definition

-- Drop table

-- DROP TABLE public.aips_external_integration_log;

CREATE TABLE public.aips_external_integration_log (
	integration_id bigserial NOT NULL,
	integration_time timestamp DEFAULT now() NULL,
	target_system varchar(80) NULL,
	direction varchar(40) NULL,
	api_name varchar(120) NULL,
	request_json jsonb NULL,
	response_json jsonb NULL,
	status varchar(40) NULL,
	message text NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_external_integration_log_pkey PRIMARY KEY (integration_id)
);


-- public.aips_file_object_log definition

-- Drop table

-- DROP TABLE public.aips_file_object_log;

CREATE TABLE public.aips_file_object_log (
	file_id bigserial NOT NULL,
	upload_time timestamp DEFAULT now() NULL,
	storage_type varchar(40) NULL,
	bucket_name varchar(120) NULL,
	object_key text NULL,
	file_name varchar(200) NULL,
	file_type varchar(80) NULL,
	related_module varchar(80) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_file_object_log_pkey PRIMARY KEY (file_id)
);


-- public.aips_gateway_device definition

-- Drop table

-- DROP TABLE public.aips_gateway_device;

CREATE TABLE public.aips_gateway_device (
	device_id bigserial NOT NULL,
	device_code varchar(80) NULL,
	device_name varchar(120) NULL,
	device_type varchar(80) NULL,
	device_ip varchar(80) NULL,
	protocol_type varchar(80) NULL,
	mqtt_topic varchar(200) NULL,
	modbus_unit_id int4 NULL,
	enabled_flag bool DEFAULT true NULL,
	last_seen_time timestamp NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_gateway_device_pkey PRIMARY KEY (device_id)
);


-- public.aips_login_log definition

-- Drop table

-- DROP TABLE public.aips_login_log;

CREATE TABLE public.aips_login_log (
	login_id bigserial NOT NULL,
	login_time timestamp DEFAULT now() NULL,
	username varchar(80) NULL,
	login_status varchar(40) NULL,
	client_ip varchar(80) NULL,
	user_agent text NULL,
	message text NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_login_log_pkey PRIMARY KEY (login_id)
);


-- public.aips_notification_log definition

-- Drop table

-- DROP TABLE public.aips_notification_log;

CREATE TABLE public.aips_notification_log (
	notification_id bigserial NOT NULL,
	notification_time timestamp DEFAULT now() NULL,
	channel_type varchar(40) NULL,
	receiver varchar(200) NULL,
	subject varchar(200) NULL,
	message_body text NULL,
	send_status varchar(40) NULL,
	related_work_order_no varchar(80) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_notification_log_pkey PRIMARY KEY (notification_id)
);


-- public.aips_pda_scan_task definition

-- Drop table

-- DROP TABLE public.aips_pda_scan_task;

CREATE TABLE public.aips_pda_scan_task (
	task_id bigserial NOT NULL,
	task_type varchar(80) NULL,
	work_order_no varchar(80) NULL,
	material_no varchar(80) NULL,
	source_location varchar(80) NULL,
	target_location varchar(80) NULL,
	task_status varchar(40) DEFAULT 'OPEN'::character varying NULL,
	assigned_user varchar(80) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_pda_scan_task_pkey PRIMARY KEY (task_id)
);


-- public.aips_product_cnc_process_assumption definition

-- Drop table

-- DROP TABLE public.aips_product_cnc_process_assumption;

CREATE TABLE public.aips_product_cnc_process_assumption (
	assumption_id bigserial NOT NULL,
	product_no varchar(80) NULL,
	product_name varchar(120) NULL,
	step_no int4 NULL,
	step_name varchar(120) NULL,
	cnc_machine_id varchar(80) NULL,
	processing_minutes int4 NULL,
	setup_minutes int4 DEFAULT 0 NULL,
	sequence_note text NULL,
	enabled_flag bool DEFAULT true NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_product_cnc_process_assumption_pkey PRIMARY KEY (assumption_id)
);
CREATE UNIQUE INDEX ux_product_cnc_process_step ON public.aips_product_cnc_process_assumption USING btree (product_no, step_no);


-- public.aips_production_prediction definition

-- Drop table

-- DROP TABLE public.aips_production_prediction;

CREATE TABLE public.aips_production_prediction (
	prediction_id bigserial NOT NULL,
	prediction_time timestamp DEFAULT now() NULL,
	model_name varchar(120) NULL,
	model_version varchar(40) NULL,
	work_order_no varchar(80) NULL,
	product_no varchar(80) NULL,
	process_code varchar(80) NULL,
	cnc_machine_id varchar(80) NULL,
	predicted_processing_time numeric(12, 4) NULL,
	predicted_finish_time timestamp NULL,
	predicted_delay_hours numeric(12, 4) NULL,
	predicted_machine_down_risk numeric(8, 4) NULL,
	predicted_quality_risk numeric(8, 4) NULL,
	predicted_material_shortage_risk numeric(8, 4) NULL,
	predicted_energy_consumption_kwh numeric(14, 4) NULL,
	prediction_confidence_score numeric(8, 4) NULL,
	created_at timestamp DEFAULT now() NULL,
	prediction_type varchar(80) NULL,
	predicted_output_qty numeric(18, 4) NULL,
	predicted_good_qty numeric(18, 4) NULL,
	predicted_ng_qty numeric(18, 4) NULL,
	predicted_yield_rate numeric(10, 4) NULL,
	capacity_utilization_rate numeric(10, 4) NULL,
	CONSTRAINT aips_production_prediction_pkey PRIMARY KEY (prediction_id)
);


-- public.aips_realtime_event_log definition

-- Drop table

-- DROP TABLE public.aips_realtime_event_log;

CREATE TABLE public.aips_realtime_event_log (
	event_id bigserial NOT NULL,
	event_time timestamp DEFAULT now() NULL,
	event_source varchar(80) NULL,
	event_type varchar(80) NULL,
	event_level varchar(40) NULL,
	topic varchar(200) NULL,
	payload_json jsonb NULL,
	process_status varchar(40) DEFAULT 'RECEIVED'::character varying NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_realtime_event_log_pkey PRIMARY KEY (event_id)
);


-- public.aips_report_job definition

-- Drop table

-- DROP TABLE public.aips_report_job;

CREATE TABLE public.aips_report_job (
	report_job_id bigserial NOT NULL,
	report_time timestamp DEFAULT now() NULL,
	report_type varchar(80) NULL,
	report_name varchar(200) NULL,
	file_format varchar(40) NULL,
	file_path text NULL,
	job_status varchar(40) NULL,
	created_by varchar(80) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_report_job_pkey PRIMARY KEY (report_job_id)
);


-- public.aips_reward_result definition

-- Drop table

-- DROP TABLE public.aips_reward_result;

CREATE TABLE public.aips_reward_result (
	reward_id bigserial NOT NULL,
	action_id int8 NULL,
	state_id int8 NULL,
	evaluate_time timestamp DEFAULT now() NULL,
	work_order_no varchar(80) NULL,
	cnc_machine_id varchar(80) NULL,
	actual_start_time timestamp NULL,
	actual_finish_time timestamp NULL,
	actual_processing_time numeric(12, 4) NULL,
	planned_processing_time numeric(12, 4) NULL,
	delay_hours numeric(12, 4) NULL,
	shortage_occurred_flag bool NULL,
	machine_down_occurred_flag bool NULL,
	ng_qty numeric(14, 4) NULL,
	good_qty numeric(14, 4) NULL,
	actual_yield_rate numeric(8, 4) NULL,
	actual_oee numeric(8, 4) NULL,
	energy_kwh numeric(14, 4) NULL,
	reward_oee_score numeric(12, 4) NULL,
	reward_delivery_score numeric(12, 4) NULL,
	reward_shortage_score numeric(12, 4) NULL,
	reward_quality_score numeric(12, 4) NULL,
	reward_energy_score numeric(12, 4) NULL,
	total_reward_score numeric(12, 4) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_reward_result_pkey PRIMARY KEY (reward_id)
);


-- public.aips_run_card_ai_feature definition

-- Drop table

-- DROP TABLE public.aips_run_card_ai_feature;

CREATE TABLE public.aips_run_card_ai_feature (
	feature_id bigserial NOT NULL,
	feature_time timestamp DEFAULT now() NULL,
	run_card_id int8 NULL,
	run_card_detail_id int8 NULL,
	work_order_no varchar(80) NULL,
	product_no varchar(80) NULL,
	station_name varchar(120) NULL,
	cnc_machine_id varchar(80) NULL,
	sequence_no int4 NULL,
	actual_processing_minutes numeric(14, 4) NULL,
	moving_avg_processing_minutes numeric(14, 4) NULL,
	arima_predicted_minutes numeric(14, 4) NULL,
	lstm_predicted_minutes numeric(14, 4) NULL,
	predicted_finish_time timestamp NULL,
	delay_risk_score numeric(8, 4) NULL,
	shortage_risk_score numeric(8, 4) NULL,
	quality_risk_score numeric(8, 4) NULL,
	power_risk_score numeric(8, 4) NULL,
	dqn_state_json jsonb NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_run_card_ai_feature_pkey PRIMARY KEY (feature_id)
);
CREATE INDEX ix_aips_run_card_ai_feature_work_order ON public.aips_run_card_ai_feature USING btree (work_order_no);


-- public.aips_run_card_detail definition

-- Drop table

-- DROP TABLE public.aips_run_card_detail;

CREATE TABLE public.aips_run_card_detail (
	run_card_detail_id bigserial NOT NULL,
	run_card_id int8 NOT NULL,
	sequence_no int4 NOT NULL,
	station_code varchar(80) NULL,
	station_name varchar(120) NULL,
	station_sub_name varchar(120) NULL,
	process_type varchar(80) NULL,
	cnc_machine_id varchar(80) NULL,
	machine_group varchar(80) NULL,
	line_side_location_id varchar(80) NULL,
	planned_qty numeric(14, 4) NULL,
	completed_qty numeric(14, 4) DEFAULT 0 NULL,
	good_qty numeric(14, 4) DEFAULT 0 NULL,
	ng_qty numeric(14, 4) DEFAULT 0 NULL,
	control_spec_text text NULL,
	measurement_spec_text text NULL,
	standard_cycle_time_sec numeric(14, 4) NULL,
	standard_setup_time_min numeric(14, 4) NULL,
	input_time timestamp NULL,
	output_time timestamp NULL,
	actual_processing_minutes numeric(14, 4) NULL,
	wait_minutes_before_start numeric(14, 4) NULL,
	delay_minutes numeric(14, 4) NULL,
	responsible_user_id varchar(80) NULL,
	responsible_user_name varchar(120) NULL,
	sign_status varchar(40) NULL,
	confirm_flag bool DEFAULT false NULL,
	qc_result varchar(40) NULL,
	material_available_flag bool NULL,
	shortage_flag bool DEFAULT false NULL,
	shortage_qty numeric(14, 4) NULL,
	replenishment_required_flag bool DEFAULT false NULL,
	machine_status_when_start varchar(40) NULL,
	avg_power_kw numeric(14, 4) NULL,
	max_power_kw numeric(14, 4) NULL,
	avg_thd_current numeric(14, 4) NULL,
	energy_kwh numeric(14, 4) NULL,
	quality_risk_score numeric(8, 4) NULL,
	abnormal_flag bool DEFAULT false NULL,
	abnormal_reason text NULL,
	detail_status varchar(40) DEFAULT 'PENDING'::character varying NULL,
	ai_feature_ready_flag bool DEFAULT false NULL,
	remark text NULL,
	created_at timestamp DEFAULT now() NULL,
	updated_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_run_card_detail_pkey PRIMARY KEY (run_card_detail_id)
);
CREATE INDEX ix_aips_run_card_detail_card ON public.aips_run_card_detail USING btree (run_card_id);
CREATE INDEX ix_aips_run_card_detail_machine ON public.aips_run_card_detail USING btree (cnc_machine_id);
CREATE INDEX ix_aips_run_card_detail_station ON public.aips_run_card_detail USING btree (station_name);


-- public.aips_run_card_detail_item definition

-- Drop table

-- DROP TABLE public.aips_run_card_detail_item;

CREATE TABLE public.aips_run_card_detail_item (
	run_card_item_id bigserial NOT NULL,
	run_card_detail_id int8 NOT NULL,
	item_sequence_no int4 NULL,
	item_type varchar(80) NULL,
	item_code varchar(80) NULL,
	item_name varchar(200) NULL,
	tool_no varchar(80) NULL,
	tool_name varchar(120) NULL,
	pressure_name varchar(80) NULL,
	pressure_spec varchar(120) NULL,
	speed_spec varchar(120) NULL,
	planned_qty numeric(14, 4) NULL,
	control_spec_text text NULL,
	spec_upper_limit numeric(14, 4) NULL,
	spec_lower_limit numeric(14, 4) NULL,
	target_value numeric(14, 4) NULL,
	confirm_flag bool DEFAULT false NULL,
	item_result varchar(40) NULL,
	input_time timestamp NULL,
	output_time timestamp NULL,
	responsible_user_id varchar(80) NULL,
	created_at timestamp DEFAULT now() NULL,
	updated_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_run_card_detail_item_pkey PRIMARY KEY (run_card_item_id)
);


-- public.aips_run_card_header definition

-- Drop table

-- DROP TABLE public.aips_run_card_header;

CREATE TABLE public.aips_run_card_header (
	run_card_id bigserial NOT NULL,
	run_card_no varchar(80) NULL,
	production_batch_no varchar(80) NULL,
	work_order_no varchar(80) NULL,
	sales_order_no varchar(80) NULL,
	customer_name varchar(120) NULL,
	product_no varchar(80) NULL,
	material_no varchar(80) NULL,
	piece_id varchar(120) NULL,
	serial_no varchar(120) NULL,
	process_name varchar(120) NULL,
	process_level varchar(40) NULL,
	unit varchar(40) NULL,
	size_length numeric(14, 4) NULL,
	size_width numeric(14, 4) NULL,
	planned_qty numeric(14, 4) NULL,
	completed_qty numeric(14, 4) DEFAULT 0 NULL,
	good_qty numeric(14, 4) DEFAULT 0 NULL,
	ng_qty numeric(14, 4) DEFAULT 0 NULL,
	remaining_qty numeric(14, 4) NULL,
	planned_start_time timestamp NULL,
	planned_finish_time timestamp NULL,
	actual_start_time timestamp NULL,
	actual_finish_time timestamp NULL,
	due_date timestamp NULL,
	priority_level int4 DEFAULT 5 NULL,
	run_card_status varchar(40) DEFAULT 'OPEN'::character varying NULL,
	source_system varchar(40) DEFAULT 'AIPS'::character varying NULL,
	source_file_name varchar(255) NULL,
	import_batch_no varchar(80) NULL,
	remark text NULL,
	created_by varchar(80) NULL,
	created_at timestamp DEFAULT now() NULL,
	updated_by varchar(80) NULL,
	updated_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_run_card_header_pkey PRIMARY KEY (run_card_id)
);
CREATE INDEX ix_aips_run_card_header_card_no ON public.aips_run_card_header USING btree (run_card_no);
CREATE INDEX ix_aips_run_card_header_work_order ON public.aips_run_card_header USING btree (work_order_no);


-- public.aips_run_card_measurement definition

-- Drop table

-- DROP TABLE public.aips_run_card_measurement;

CREATE TABLE public.aips_run_card_measurement (
	measurement_id bigserial NOT NULL,
	run_card_detail_id int8 NOT NULL,
	run_card_item_id int8 NULL,
	measure_time timestamp DEFAULT now() NULL,
	measure_source varchar(40) NULL,
	measure_device_id varchar(80) NULL,
	cnc_machine_id varchar(80) NULL,
	measure_name varchar(120) NULL,
	measure_value numeric(18, 6) NULL,
	measure_unit varchar(40) NULL,
	target_value numeric(18, 6) NULL,
	upper_limit numeric(18, 6) NULL,
	lower_limit numeric(18, 6) NULL,
	deviation_value numeric(18, 6) NULL,
	pass_flag bool NULL,
	quality_risk_score numeric(8, 4) NULL,
	raw_measure_text text NULL,
	raw_payload jsonb NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_run_card_measurement_pkey PRIMARY KEY (measurement_id)
);


-- public.aips_scan_event definition

-- Drop table

-- DROP TABLE public.aips_scan_event;

CREATE TABLE public.aips_scan_event (
	scan_event_id bigserial NOT NULL,
	scan_time timestamp DEFAULT now() NULL,
	scan_type varchar(80) NULL,
	scan_code varchar(200) NULL,
	operator_id varchar(80) NULL,
	work_order_no varchar(80) NULL,
	material_no varchar(80) NULL,
	cnc_machine_id varchar(80) NULL,
	event_status varchar(40) NULL,
	event_message text NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_scan_event_pkey PRIMARY KEY (scan_event_id)
);


-- public.aips_scheduling_state definition

-- Drop table

-- DROP TABLE public.aips_scheduling_state;

CREATE TABLE public.aips_scheduling_state (
	state_id bigserial NOT NULL,
	state_time timestamp DEFAULT now() NULL,
	work_order_no varchar(80) NULL,
	product_no varchar(80) NULL,
	process_code varchar(80) NULL,
	cnc_machine_id varchar(80) NULL,
	machine_status varchar(40) NULL,
	machine_available_flag bool NULL,
	machine_load_rate numeric(8, 4) NULL,
	estimated_processing_time numeric(12, 4) NULL,
	estimated_finish_time timestamp NULL,
	line_side_material_available_flag bool NULL,
	line_side_shortage_qty numeric(14, 4) NULL,
	remaining_order_qty numeric(14, 4) NULL,
	due_date timestamp NULL,
	remaining_days_to_due numeric(12, 4) NULL,
	order_priority_score numeric(8, 4) NULL,
	delay_risk_score numeric(8, 4) NULL,
	shortage_risk_score numeric(8, 4) NULL,
	power_consumption_level numeric(12, 4) NULL,
	abnormal_power_flag bool NULL,
	quality_risk_score numeric(8, 4) NULL,
	current_oee numeric(8, 4) NULL,
	current_availability_rate numeric(8, 4) NULL,
	current_performance_rate numeric(8, 4) NULL,
	current_yield_rate numeric(8, 4) NULL,
	state_vector_json jsonb NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_scheduling_state_pkey PRIMARY KEY (state_id)
);


-- public.aips_shortage_priority_decision definition

-- Drop table

-- DROP TABLE public.aips_shortage_priority_decision;

CREATE TABLE public.aips_shortage_priority_decision (
	decision_id bigserial NOT NULL,
	decision_time timestamp DEFAULT now() NULL,
	state_id int8 NULL,
	work_order_no varchar(80) NULL,
	product_no varchar(80) NULL,
	cnc_machine_id varchar(80) NULL,
	customer_shortage_risk_score numeric(10, 4) NULL,
	line_side_shortage_qty numeric(14, 4) NULL,
	available_stock_qty numeric(14, 4) NULL,
	demand_qty numeric(14, 4) NULL,
	shortage_qty numeric(14, 4) NULL,
	due_date_remaining_hours numeric(12, 4) NULL,
	avg_oee numeric(10, 4) NULL,
	avg_power_demand numeric(12, 4) NULL,
	quality_risk_score numeric(10, 4) NULL,
	base_q_json jsonb NULL,
	adjusted_q_json jsonb NULL,
	selected_action_type varchar(80) NULL,
	selected_action_name varchar(120) NULL,
	selected_q_value numeric(14, 4) NULL,
	shortage_priority_bonus numeric(14, 4) NULL,
	shortage_penalty numeric(14, 4) NULL,
	decision_reason text NULL,
	model_version varchar(80) DEFAULT 'SHORTAGE_PRIORITY_DQN_V1'::character varying NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_shortage_priority_decision_pkey PRIMARY KEY (decision_id)
);
CREATE INDEX ix_aips_shortage_priority_decision_risk ON public.aips_shortage_priority_decision USING btree (customer_shortage_risk_score DESC);
CREATE INDEX ix_aips_shortage_priority_decision_state ON public.aips_shortage_priority_decision USING btree (state_id);
CREATE INDEX ix_shortage_priority_decision_risk ON public.aips_shortage_priority_decision USING btree (customer_shortage_risk_score);
CREATE INDEX ix_shortage_priority_decision_time ON public.aips_shortage_priority_decision USING btree (decision_time);


-- public.aips_shortage_priority_experience definition

-- Drop table

-- DROP TABLE public.aips_shortage_priority_experience;

CREATE TABLE public.aips_shortage_priority_experience (
	experience_id bigserial NOT NULL,
	state_id int8 NULL,
	decision_id int8 NULL,
	action_type varchar(80) NULL,
	reward_value numeric(14, 4) NULL,
	next_state_id int8 NULL,
	experience_json jsonb NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_shortage_priority_experience_pkey PRIMARY KEY (experience_id)
);


-- public.aips_sim_cnc_smart_meter definition

-- Drop table

-- DROP TABLE public.aips_sim_cnc_smart_meter;

CREATE TABLE public.aips_sim_cnc_smart_meter (
	sim_meter_id bigserial NOT NULL,
	cnc_machine_id varchar(80) NULL,
	meter_id varchar(80) NULL,
	device_ip varchar(80) NULL,
	protocol_type varchar(80) NULL,
	modbus_unit_id int4 NULL,
	mqtt_topic varchar(200) NULL,
	voltage_v numeric(12, 4) NULL,
	current_a numeric(12, 4) NULL,
	power_kw numeric(12, 4) NULL,
	demand_kw numeric(12, 4) NULL,
	thd_current numeric(8, 4) NULL,
	machine_status varchar(40) NULL,
	online_flag bool DEFAULT true NULL,
	last_collect_time timestamp NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_sim_cnc_smart_meter_pkey PRIMARY KEY (sim_meter_id)
);


-- public.aips_sim_line_side_logistics definition

-- Drop table

-- DROP TABLE public.aips_sim_line_side_logistics;

CREATE TABLE public.aips_sim_line_side_logistics (
	logistics_id bigserial NOT NULL,
	event_time timestamp DEFAULT now() NULL,
	cart_code varchar(80) NULL,
	operator_id varchar(80) NULL,
	work_order_no varchar(80) NULL,
	material_no varchar(80) NULL,
	from_location varchar(80) NULL,
	to_location varchar(80) NULL,
	logistics_action varchar(80) NULL,
	qty numeric(14, 4) NULL,
	event_status varchar(40) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_sim_line_side_logistics_pkey PRIMARY KEY (logistics_id)
);


-- public.aips_sim_nfc_qrcode_tag definition

-- Drop table

-- DROP TABLE public.aips_sim_nfc_qrcode_tag;

CREATE TABLE public.aips_sim_nfc_qrcode_tag (
	tag_id bigserial NOT NULL,
	tag_code varchar(200) NULL,
	tag_type varchar(80) NULL,
	bind_target_type varchar(80) NULL,
	bind_target_code varchar(120) NULL,
	bind_target_name varchar(200) NULL,
	enabled_flag bool DEFAULT true NULL,
	last_scan_time timestamp NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_sim_nfc_qrcode_tag_pkey PRIMARY KEY (tag_id)
);


-- public.aips_sim_pda_device definition

-- Drop table

-- DROP TABLE public.aips_sim_pda_device;

CREATE TABLE public.aips_sim_pda_device (
	pda_id bigserial NOT NULL,
	device_code varchar(80) NULL,
	device_name varchar(120) NULL,
	device_type varchar(80) NULL,
	wifi_ssid varchar(120) NULL,
	ip_address varchar(80) NULL,
	operator_id varchar(80) NULL,
	online_flag bool DEFAULT true NULL,
	last_scan_time timestamp NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_sim_pda_device_pkey PRIMARY KEY (pda_id)
);


-- public.aips_user_account definition

-- Drop table

-- DROP TABLE public.aips_user_account;

CREATE TABLE public.aips_user_account (
	user_id bigserial NOT NULL,
	username varchar(80) NOT NULL,
	display_name varchar(120) NULL,
	role_name varchar(80) NULL,
	permission_json jsonb NULL,
	enabled_flag bool DEFAULT true NULL,
	password_text varchar(120) DEFAULT '123456'::character varying NULL,
	last_login_time timestamp NULL,
	updated_at timestamp NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_user_account_pkey PRIMARY KEY (user_id),
	CONSTRAINT aips_user_account_username_key UNIQUE (username)
);
CREATE UNIQUE INDEX ux_aips_user_account_username ON public.aips_user_account USING btree (username);


-- public.aips_websocket_push_log definition

-- Drop table

-- DROP TABLE public.aips_websocket_push_log;

CREATE TABLE public.aips_websocket_push_log (
	push_id bigserial NOT NULL,
	push_time timestamp DEFAULT now() NULL,
	channel_name varchar(120) NULL,
	target_user varchar(80) NULL,
	message_title varchar(200) NULL,
	message_body text NULL,
	push_status varchar(40) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT aips_websocket_push_log_pkey PRIMARY KEY (push_id)
);


-- public.cnc_machine_status_snapshot definition

-- Drop table

-- DROP TABLE public.cnc_machine_status_snapshot;

CREATE TABLE public.cnc_machine_status_snapshot (
	snapshot_id bigserial NOT NULL,
	cnc_machine_id varchar(80) NULL,
	snapshot_time timestamp DEFAULT now() NULL,
	machine_status varchar(40) NULL,
	current_work_order_no varchar(80) NULL,
	current_product_no varchar(80) NULL,
	current_process_code varchar(80) NULL,
	operator_id varchar(80) NULL,
	running_minutes_today numeric(12, 4) NULL,
	idle_minutes_today numeric(12, 4) NULL,
	down_minutes_today numeric(12, 4) NULL,
	setup_minutes_today numeric(12, 4) NULL,
	avg_power_kw numeric(12, 4) NULL,
	current_load_level numeric(8, 4) NULL,
	estimated_finish_time timestamp NULL,
	abnormal_flag bool DEFAULT false NULL,
	abnormal_reason text NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT cnc_machine_status_snapshot_pkey PRIMARY KEY (snapshot_id)
);


-- public.cnc_meter_feature definition

-- Drop table

-- DROP TABLE public.cnc_meter_feature;

CREATE TABLE public.cnc_meter_feature (
	feature_id bigserial NOT NULL,
	cnc_machine_id varchar(80) NULL,
	feature_time timestamp DEFAULT now() NULL,
	avg_power_kw_1min numeric(12, 4) NULL,
	avg_power_kw_5min numeric(12, 4) NULL,
	avg_power_kw_15min numeric(12, 4) NULL,
	max_power_kw numeric(12, 4) NULL,
	min_power_kw numeric(12, 4) NULL,
	power_variation_rate numeric(12, 4) NULL,
	avg_current_a numeric(12, 4) NULL,
	current_variation_rate numeric(12, 4) NULL,
	energy_kwh_1hr numeric(14, 4) NULL,
	demand_kw_15min numeric(12, 4) NULL,
	thd_current_avg numeric(8, 4) NULL,
	machine_running_flag bool DEFAULT false NULL,
	machine_idle_flag bool DEFAULT false NULL,
	machine_abnormal_power_flag bool DEFAULT false NULL,
	estimated_machine_status varchar(40) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT cnc_meter_feature_pkey PRIMARY KEY (feature_id)
);


-- public.cnc_meter_raw_data definition

-- Drop table

-- DROP TABLE public.cnc_meter_raw_data;

CREATE TABLE public.cnc_meter_raw_data (
	meter_data_id bigserial NOT NULL,
	meter_id varchar(80) NULL,
	cnc_machine_id varchar(80) NULL,
	device_ip varchar(80) NULL,
	mqtt_topic varchar(200) NULL,
	collect_time timestamp DEFAULT now() NULL,
	voltage_r numeric(12, 4) NULL,
	voltage_s numeric(12, 4) NULL,
	voltage_t numeric(12, 4) NULL,
	current_r numeric(12, 4) NULL,
	current_s numeric(12, 4) NULL,
	current_t numeric(12, 4) NULL,
	power_kw numeric(12, 4) NULL,
	power_kwh numeric(14, 4) NULL,
	power_factor numeric(8, 4) NULL,
	frequency_hz numeric(8, 4) NULL,
	demand_kw numeric(12, 4) NULL,
	thd_voltage numeric(8, 4) NULL,
	thd_current numeric(8, 4) NULL,
	phase_imbalance_rate numeric(8, 4) NULL,
	raw_payload jsonb NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT cnc_meter_raw_data_pkey PRIMARY KEY (meter_data_id)
);


-- public.line_side_inventory_snapshot definition

-- Drop table

-- DROP TABLE public.line_side_inventory_snapshot;

CREATE TABLE public.line_side_inventory_snapshot (
	snapshot_id bigserial NOT NULL,
	snapshot_time timestamp DEFAULT now() NULL,
	cnc_machine_id varchar(80) NULL,
	line_side_location_id varchar(80) NULL,
	material_no varchar(80) NULL,
	material_name varchar(200) NULL,
	lot_no varchar(80) NULL,
	current_qty numeric(14, 4) NULL,
	reserved_qty numeric(14, 4) NULL,
	available_qty numeric(14, 4) NULL,
	safety_stock_qty numeric(14, 4) NULL,
	shortage_flag bool DEFAULT false NULL,
	shortage_qty numeric(14, 4) NULL,
	replenishment_required_flag bool DEFAULT false NULL,
	last_scan_time timestamp NULL,
	source_system varchar(40) NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT line_side_inventory_snapshot_pkey PRIMARY KEY (snapshot_id)
);


-- public.work_order_progress_snapshot definition

-- Drop table

-- DROP TABLE public.work_order_progress_snapshot;

CREATE TABLE public.work_order_progress_snapshot (
	snapshot_id bigserial NOT NULL,
	snapshot_time timestamp DEFAULT now() NULL,
	work_order_no varchar(80) NULL,
	sales_order_no varchar(80) NULL,
	customer_id varchar(80) NULL,
	product_no varchar(80) NULL,
	product_name varchar(200) NULL,
	process_code varchar(80) NULL,
	planned_qty numeric(14, 4) NULL,
	completed_qty numeric(14, 4) NULL,
	good_qty numeric(14, 4) NULL,
	ng_qty numeric(14, 4) NULL,
	remaining_qty numeric(14, 4) NULL,
	due_date timestamp NULL,
	priority_level int4 NULL,
	current_process_status varchar(40) NULL,
	assigned_cnc_machine_id varchar(80) NULL,
	estimated_remaining_hours numeric(12, 4) NULL,
	delay_risk_flag bool DEFAULT false NULL,
	created_at timestamp DEFAULT now() NULL,
	CONSTRAINT work_order_progress_snapshot_pkey PRIMARY KEY (snapshot_id)
);