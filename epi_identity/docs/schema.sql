-- Schema de referência (PostgreSQL) gerado dos modelos SQLAlchemy.
-- Em producao, versione via Alembic.

CREATE TABLE audit_logs (
	action VARCHAR(50) NOT NULL, 
	actor VARCHAR(100) NOT NULL, 
	actor_role VARCHAR(30), 
	resource_type VARCHAR(50), 
	resource_id VARCHAR(64), 
	ip_address VARCHAR(64), 
	details JSON, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_audit_logs_action ON audit_logs (action);

CREATE INDEX ix_audit_logs_actor ON audit_logs (actor);

CREATE INDEX ix_audit_logs_resource_id ON audit_logs (resource_id);

CREATE TABLE employees (
	employee_code VARCHAR(20) NOT NULL, 
	registration VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	sector VARCHAR(100) NOT NULL, 
	role_title VARCHAR(100) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	biometric_status VARCHAR(20) NOT NULL, 
	biometric_consent BOOLEAN NOT NULL, 
	biometric_consent_at TIMESTAMP WITH TIME ZONE, 
	is_deleted BOOLEAN NOT NULL, 
	deleted_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_employee_status_active ON employees (status, is_deleted);

CREATE UNIQUE INDEX ix_employees_employee_code ON employees (employee_code);

CREATE INDEX ix_employees_is_deleted ON employees (is_deleted);

CREATE INDEX ix_employees_registration ON employees (registration);

CREATE TABLE person_tracks (
	track_code VARCHAR(64) NOT NULL, 
	camera_id VARCHAR(50) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	employee_code VARCHAR(20), 
	identity_status VARCHAR(20) NOT NULL, 
	identity_confidence FLOAT, 
	first_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	last_seen_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	closed_at TIMESTAMP WITH TIME ZONE, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_person_tracks_camera_id ON person_tracks (camera_id);

CREATE INDEX ix_person_tracks_employee_code ON person_tracks (employee_code);

CREATE UNIQUE INDEX ix_person_tracks_track_code ON person_tracks (track_code);

CREATE TABLE employee_biometrics (
	employee_id VARCHAR(36) NOT NULL, 
	embedding_encrypted BYTEA NOT NULL, 
	embedding_dim INTEGER NOT NULL, 
	model_version VARCHAR(50) NOT NULL, 
	quality_score FLOAT NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	enrolled_by VARCHAR(100), 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employee_id) REFERENCES employees (id)
);

CREATE INDEX ix_employee_biometrics_employee_id ON employee_biometrics (employee_id);

CREATE INDEX ix_employee_biometrics_is_active ON employee_biometrics (is_active);

CREATE INDEX ix_employee_biometrics_model_version ON employee_biometrics (model_version);

CREATE TABLE face_recognition_events (
	camera_id VARCHAR(50) NOT NULL, 
	person_track_id VARCHAR(36), 
	employee_code VARCHAR(20), 
	status VARCHAR(20) NOT NULL, 
	quality_score FLOAT, 
	similarity_score FLOAT, 
	confidence_score FLOAT, 
	runner_up_code VARCHAR(20), 
	runner_up_similarity FLOAT, 
	model_version VARCHAR(50), 
	requires_review BOOLEAN NOT NULL, 
	processing_ms FLOAT, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(person_track_id) REFERENCES person_tracks (id)
);

CREATE INDEX ix_face_recognition_events_camera_id ON face_recognition_events (camera_id);

CREATE INDEX ix_face_recognition_events_employee_code ON face_recognition_events (employee_code);

CREATE INDEX ix_face_recognition_events_person_track_id ON face_recognition_events (person_track_id);

CREATE INDEX ix_face_recognition_events_requires_review ON face_recognition_events (requires_review);

CREATE INDEX ix_face_recognition_events_status ON face_recognition_events (status);

CREATE TABLE recognition_reviews (
	event_id VARCHAR(36) NOT NULL, 
	decision VARCHAR(20) NOT NULL, 
	reviewer VARCHAR(100) NOT NULL, 
	final_employee_code VARCHAR(20), 
	notes TEXT, 
	id VARCHAR(36) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_id) REFERENCES face_recognition_events (id)
);

CREATE INDEX ix_recognition_reviews_event_id ON recognition_reviews (event_id);
