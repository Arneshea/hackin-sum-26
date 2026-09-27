-- =====================================================================
-- 001_init_schema.sql
--
-- National Patient Navigation & Referral Coordination Network
-- Core schema migration for Supabase PostgreSQL.
--
-- Scope: this migration implements the tables required for the
-- end-to-end demo path (BUILD_SPEC section 45 / section 28 core
-- demo scenario). It intentionally follows the five-state-machine
-- separation mandated in section 0.1:
--
--   1. journeys                (PATIENT JOURNEY)
--   2. patient_requests /
--      patient_request_responses (STAGE-1 PATIENT<->HOSPITAL MATCH)
--   3. hospital_state           (HOSPITAL OPERATIONAL STATE)
--   4. referrals /
--      referral_responses      (STAGE-2 HOSPITAL<->HOSPITAL REFERRAL)
--   5. transfers / handoffs     (TRANSFER / HANDOFF)
--
-- Run with the Supabase CLI:
--   supabase db push
-- or paste into the Supabase SQL editor in migration order.
-- =====================================================================

create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- Enumerated types
-- ---------------------------------------------------------------------

create type user_role as enum ('PATIENT', 'DOCTOR', 'HOSPITAL_STAFF', 'NETWORK_ADMIN');

create type journey_status as enum (
  'AT_HOME',
  'REQUESTING_HOSPITAL',
  'MATCHED_TO_HOSPITAL_1',
  'EN_ROUTE_TO_HOSPITAL_1',
  'ARRIVED_AT_HOSPITAL_1',
  'UNDER_CARE',
  'REFERRAL_INITIATED',
  'TRANSFER_TO_HOSPITAL_2',
  'COMPLETED',
  'CANCELLED'
);

create type patient_request_status as enum (
  'DRAFT',
  'SUBMITTED',
  'BROADCASTING',
  'PATIENT_SELECTING',
  'CONFIRMING',
  'MATCHED',
  'NO_MATCH',
  'EXPIRED',
  'CANCELLED',
  'CONFIRMATION_FAILED'
);

create type request_response_status as enum (
  'PENDING', 'ACCEPTED', 'DECLINED', 'WITHDRAWN', 'EXPIRED'
);

create type measurement_type as enum (
  'COUNT', 'BINARY_SERVICE', 'PERSONNEL_AVAILABILITY'
);

create type freshness_category as enum (
  'CURRENT', 'RECENT', 'STALE', 'UNKNOWN'
);

create type referral_status as enum (
  'DRAFT',
  'EVALUATING',
  'PENDING_ACCEPTANCE',
  'BROADCASTING',
  'ACCEPTED',
  'DECLINED_ALL',
  'NO_VERIFIED_FEASIBLE_DESTINATION',
  'CANCELLED',
  'EXPIRED'
);

create type referral_response_status as enum (
  'PENDING', 'ACCEPTED', 'DECLINED', 'EXPIRED'
);

create type decline_reason as enum (
  'ICU_UNAVAILABLE',
  'SPECIALIST_UNAVAILABLE',
  'DIAGNOSTIC_UNAVAILABLE',
  'CAPACITY_UNAVAILABLE',
  'OTHER'
);

create type transfer_status as enum (
  'ACCEPTED',
  'TRANSFER_INITIATED',
  'EN_ROUTE',
  'PATIENT_RECEIVED',
  'HANDOFF_COMPLETED'
);

create type requirement_operator as enum ('EQUALS', 'GTE', 'LTE', 'PRESENT');

-- ---------------------------------------------------------------------
-- Users (mirrors auth.users; app-level role/hospital linkage)
-- ---------------------------------------------------------------------

create table app_users (
  id uuid primary key references auth.users(id) on delete cascade,
  role user_role not null,
  hospital_id uuid null,           -- set for HOSPITAL_STAFF / DOCTOR
  display_name text not null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Hospitals: stable facility identity only (section 11 / step 2.1)
-- ---------------------------------------------------------------------

create table hospitals (
  id uuid primary key default uuid_generate_v4(),
  name text not null,
  address text not null,
  latitude double precision not null,
  longitude double precision not null,
  type text not null default 'GENERAL',
  external_registry_id_optional text null,
  is_synthetic boolean not null default true, -- prototype data rule (section 23)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table app_users
  add constraint app_users_hospital_fk foreign key (hospital_id) references hospitals(id);

-- Relatively stable capabilities (step 2.2)
create table hospital_capabilities (
  id uuid primary key default uuid_generate_v4(),
  hospital_id uuid not null references hospitals(id) on delete cascade,
  capability text not null, -- e.g. EMERGENCY, ICU, CARDIOLOGY, NEUROLOGY, CT, MRI, VENTILATOR_SUPPORT
  unique (hospital_id, capability)
);

-- Resource inventory definition (step 2.3)
create table hospital_resources (
  id uuid primary key default uuid_generate_v4(),
  hospital_id uuid not null references hospitals(id) on delete cascade,
  resource_type text not null, -- e.g. ICU, NEUROLOGY_SPECIALIST, CT
  measurement_type measurement_type not null,
  total_count_optional integer null,
  unique (hospital_id, resource_type)
);

-- Latest known operational observation (step 2.4)
create table hospital_state (
  id uuid primary key default uuid_generate_v4(),
  hospital_id uuid not null references hospitals(id) on delete cascade,
  resource_type text not null,
  measurement_type measurement_type not null,
  status text not null, -- meaning depends on measurement_type; validated in application layer
  available_count_optional integer null,
  total_count_optional integer null,
  updated_at timestamptz not null default now(),
  source text not null default 'SIMULATOR',
  source_event_id text not null,
  version bigint not null default 1,
  unique (hospital_id, resource_type)
);

create index idx_hospital_state_hospital on hospital_state(hospital_id);

-- Append-only history of accepted state changes (step 2.5 / section 41U)
create table hospital_state_events (
  event_id uuid primary key default uuid_generate_v4(),
  hospital_id uuid not null references hospitals(id) on delete cascade,
  resource_type text not null,
  event_type text not null default 'STATE_UPDATE',
  old_value jsonb null,
  new_value jsonb not null,
  event_timestamp timestamptz not null default now(),
  source text not null default 'SIMULATOR',
  source_event_id text not null,
  version bigint not null,
  created_at timestamptz not null default now(),
  unique (hospital_id, resource_type, source, source_event_id) -- idempotency key
);

create index idx_hse_hospital on hospital_state_events(hospital_id, event_timestamp desc);

-- ---------------------------------------------------------------------
-- Patients (step 4.2) — no permanent location on the profile
-- ---------------------------------------------------------------------

create table patients (
  id uuid primary key default uuid_generate_v4(),
  display_name text not null,
  age integer null,
  sex text null,
  abha_id_optional text null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Assessments (step 4.3) — Stage-1 triage output, never a diagnosis
-- ---------------------------------------------------------------------

create table assessments (
  id uuid primary key default uuid_generate_v4(),
  patient_id uuid not null references patients(id) on delete cascade,
  raw_input text not null,
  triage_label text not null,        -- e.g. urgent / consult_gp / self_monitor / ASSESSMENT_UNAVAILABLE
  model_name text not null,
  model_version text not null,
  model_scores_optional jsonb null,  -- only populated if the model exposes real scores
  policy_version text not null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Journeys — the parent workflow linking the complete patient path
-- (section 0.2 / step 4.9)
-- ---------------------------------------------------------------------

create table journeys (
  journey_id uuid primary key default uuid_generate_v4(),
  patient_id uuid not null references patients(id) on delete cascade,
  stage1_request_id uuid null,
  stage1_hospital_id uuid null references hospitals(id),
  referral_id uuid null,
  stage2_hospital_id uuid null references hospitals(id),
  current_stage text not null default 'STAGE1',
  current_status journey_status not null default 'AT_HOME',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Stage-1: patient requests (step 4.10)
-- ---------------------------------------------------------------------

create table patient_requests (
  id uuid primary key default uuid_generate_v4(),
  journey_id uuid not null references journeys(journey_id) on delete cascade,
  patient_id uuid not null references patients(id) on delete cascade,
  requester_user_id_optional uuid null references auth.users(id),
  requester_role_optional user_role null,
  urgency text not null,
  location_lat double precision not null,
  location_lon double precision not null,
  symptom_summary text not null,
  requirements_snapshot jsonb not null default '[]'::jsonb,
  status patient_request_status not null default 'DRAFT',
  created_at timestamptz not null default now(),
  expires_at timestamptz null,
  selection_expires_at timestamptz null,
  confirmation_expires_at timestamptz null,
  selected_hospital_id_optional uuid null references hospitals(id),
  matched_hospital_id_optional uuid null references hospitals(id),
  version bigint not null default 1
);

alter table journeys
  add constraint journeys_stage1_request_fk foreign key (stage1_request_id) references patient_requests(id);

create index idx_patient_requests_patient on patient_requests(patient_id);
create index idx_patient_requests_status on patient_requests(status);

-- Only one active request per patient unless the product explicitly
-- allows more (section 41P). Enforced partially here; also checked
-- in the application layer for the statuses that count as "active".
create unique index uq_one_active_request_per_patient
  on patient_requests(patient_id)
  where status in ('DRAFT','SUBMITTED','BROADCASTING','PATIENT_SELECTING','CONFIRMING');

-- Stage-1 hospital responses (step 4.11)
create table patient_request_responses (
  id uuid primary key default uuid_generate_v4(),
  request_id uuid not null references patient_requests(id) on delete cascade,
  hospital_id uuid not null references hospitals(id),
  status request_response_status not null default 'PENDING',
  response_reason text null,
  responded_at timestamptz null,
  expires_at timestamptz null,
  state_version_seen bigint null,
  travel_seconds_optional integer null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (request_id, hospital_id)
);

create index idx_prr_request on patient_request_responses(request_id);

-- ---------------------------------------------------------------------
-- Stage-2: referrals (step 5.4)
-- ---------------------------------------------------------------------

create table referrals (
  id uuid primary key default uuid_generate_v4(),
  journey_id uuid not null references journeys(journey_id) on delete cascade,
  patient_id uuid not null references patients(id) on delete cascade,
  -- Nullable: a referral is now normally initiated by the patient/
  -- attendant themselves (product decision, see docs/DECISIONS.md),
  -- so there is often no "referring hospital" at all — only a
  -- referring doctor's name captured as free text below.
  referring_hospital_id uuid null references hospitals(id),
  initiated_by text not null default 'PATIENT', -- 'PATIENT' | 'HOSPITAL'
  referring_doctor_name text null,
  origin_lat double precision null,
  origin_lon double precision null,
  source_document_note text null, -- e.g. "extracted from scanned referral letter"
  urgency text not null,
  reason_for_referral text not null,
  clinical_summary text not null,
  created_by uuid null references auth.users(id),
  created_at timestamptz not null default now(),
  expires_at timestamptz null,
  status referral_status not null default 'DRAFT',
  version bigint not null default 1,
  accepted_by_hospital_id_optional uuid null references hospitals(id),
  accepted_at_optional timestamptz null
);

alter table journeys
  add constraint journeys_referral_fk foreign key (referral_id) references referrals(id);

create index idx_referrals_journey on referrals(journey_id);
create index idx_referrals_status on referrals(status);

create table referral_requirements (
  id uuid primary key default uuid_generate_v4(),
  referral_id uuid not null references referrals(id) on delete cascade,
  requirement_type text not null,     -- e.g. ICU, NEUROLOGY, CT
  value_optional text null,
  operator requirement_operator not null default 'PRESENT',
  quantity_optional integer null,
  mandatory boolean not null default true
);

create table referral_responses (
  id uuid primary key default uuid_generate_v4(),
  referral_id uuid not null references referrals(id) on delete cascade,
  hospital_id uuid not null references hospitals(id),
  status referral_response_status not null default 'PENDING',
  reason decline_reason null,
  responded_at timestamptz null,
  expires_at timestamptz null,
  unique (referral_id, hospital_id)
);

-- Reproducible ranking/eligibility evaluations (step 6.9 / section 0.9)
create table referral_evaluations (
  id uuid primary key default uuid_generate_v4(),
  referral_id uuid not null references referrals(id) on delete cascade,
  policy_version text not null,
  evaluated_at timestamptz not null default now(),
  hospital_id uuid not null references hospitals(id),
  eligible boolean not null,
  rejection_reason_optional text null,
  score_optional double precision null,
  factors_json jsonb null,
  state_versions_json jsonb null,
  routing_snapshot_json jsonb null
);

create index idx_referral_eval_referral on referral_evaluations(referral_id, evaluated_at desc);

-- ---------------------------------------------------------------------
-- Transfer / handoff (step 9.1 / 9.2)
-- ---------------------------------------------------------------------

create table transfers (
  id uuid primary key default uuid_generate_v4(),
  referral_id uuid not null references referrals(id) on delete cascade,
  journey_id uuid not null references journeys(journey_id) on delete cascade,
  status transfer_status not null default 'ACCEPTED',
  started_at timestamptz null,
  en_route_at timestamptz null,
  received_at timestamptz null,
  handoff_completed_at timestamptz null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table handoffs (
  id uuid primary key default uuid_generate_v4(),
  referral_id uuid not null references referrals(id) on delete cascade,
  patient_id uuid not null references patients(id) on delete cascade,
  clinical_summary text not null,
  current_condition text not null,
  required_specialty text null,
  required_resources text null,
  relevant_investigations text null,
  referring_doctor text not null,
  completed_by uuid null references auth.users(id),
  completed_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------
-- Emergency dispatch (new requirement: a visible, always-available
-- "Emergency" action that skips triage/matching entirely and just
-- dispatches the nearest capable hospital's ambulance). Kept as its
-- own append-mostly record, separate from the negotiated Stage-1
-- patient_requests flow, since it is deliberately NOT a negotiation —
-- no hospital accept/decline step, no patient selection step.
-- ---------------------------------------------------------------------

create table emergency_dispatches (
  id uuid primary key default uuid_generate_v4(),
  journey_id uuid not null references journeys(journey_id) on delete cascade,
  patient_id uuid not null references patients(id) on delete cascade,
  location_lat double precision not null,
  location_lon double precision not null,
  dispatched_hospital_id uuid null references hospitals(id),
  routing_source text null, -- 'OSRM' | 'GEOGRAPHIC_FALLBACK' | 'UNAVAILABLE'
  travel_seconds_optional double precision null,
  status text not null default 'DISPATCHED', -- DISPATCHED | NO_HOSPITAL_FOUND
  created_at timestamptz not null default now()
);

create index idx_emergency_dispatches_patient on emergency_dispatches(patient_id);

-- ---------------------------------------------------------------------
-- Audit trail (section 20)
-- ---------------------------------------------------------------------

create table audit_events (
  id uuid primary key default uuid_generate_v4(),
  actor_id uuid null references auth.users(id),
  actor_role user_role null,
  action text not null,
  entity_type text not null,
  entity_id uuid null,
  timestamp timestamptz not null default now(),
  metadata jsonb null
);

create index idx_audit_entity on audit_events(entity_type, entity_id);

-- ---------------------------------------------------------------------
-- Prototype configuration (section 0.10) — not scattered through code
-- ---------------------------------------------------------------------

create table prototype_config (
  key text primary key,
  value jsonb not null,
  updated_at timestamptz not null default now()
);

insert into prototype_config (key, value) values
  ('candidate_search_radius_km', '25'),
  ('stage1_response_timeout_seconds', '120'),
  ('stage1_selection_timeout_seconds', '300'),
  ('stage1_confirmation_timeout_seconds', '60'),
  ('stage2_response_timeout_seconds', '180'),
  ('stale_data_threshold_seconds', '{"current": 60, "recent": 300, "stale": 1800}'),
  ('ranking_weights_v1', '{"travel_time": 0.35, "resource_headroom": 0.30, "specialist_availability": 0.20, "state_freshness": 0.15}'),
  ('ranking_tie_breakers', '["freshness","travel_time","hospital_id"]'),
  ('routing_fallback_policy', '"GEOGRAPHIC_DISTANCE"'),
  ('stage1_broadcast_top_n', '5'),
  ('stage2_broadcast_top_n', '5')
on conflict (key) do nothing;

-- ---------------------------------------------------------------------
-- updated_at maintenance trigger
-- ---------------------------------------------------------------------

create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger trg_hospitals_updated_at before update on hospitals
  for each row execute function set_updated_at();
create trigger trg_journeys_updated_at before update on journeys
  for each row execute function set_updated_at();
create trigger trg_prr_updated_at before update on patient_request_responses
  for each row execute function set_updated_at();
create trigger trg_transfers_updated_at before update on transfers
  for each row execute function set_updated_at();
