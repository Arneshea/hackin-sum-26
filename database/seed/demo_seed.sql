-- =====================================================================
-- demo_seed.sql
--
-- Seeds exactly the entities needed for the section 28 core demo
-- scenario and the section 45 Definition-of-Done walkthrough.
-- All data here is synthetic prototype data (section 6.6 / 23) and
-- must never be presented as real hospital capacity.
--
-- Run after 001_init_schema.sql and 002/003 have been applied:
--   psql "$SUPABASE_DB_URL" -f database/seed/demo_seed.sql
-- =====================================================================

-- ---------------------------------------------------------------------
-- Three demo hospitals around a fictional metro area (coordinates are
-- illustrative, not tied to any real facility).
-- ---------------------------------------------------------------------

insert into hospitals (id, name, address, latitude, longitude, type, is_synthetic) values
  ('11111111-1111-1111-1111-111111111111', 'Hospital A (Demo)', '12 Prototype Ave, Demo City', 28.6139, 77.2090, 'MULTI_SPECIALTY', true),
  ('22222222-2222-2222-2222-222222222222', 'Hospital B (Demo)', '45 Prototype Ave, Demo City', 28.6304, 77.2177, 'MULTI_SPECIALTY', true),
  ('33333333-3333-3333-3333-333333333333', 'Hospital C (Demo)', '9 Prototype Ave, Demo City',  28.5921, 77.2000, 'MULTI_SPECIALTY', true)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------
-- Capabilities: all three can take a general emergency; only A and C
-- initially hold ICU + NEUROLOGY + CT together (B is missing ICU
-- capacity later, not capability, per the section 28 scenario).
-- ---------------------------------------------------------------------

insert into hospital_capabilities (hospital_id, capability) values
  ('11111111-1111-1111-1111-111111111111', 'EMERGENCY'),
  ('11111111-1111-1111-1111-111111111111', 'ICU'),
  ('11111111-1111-1111-1111-111111111111', 'NEUROLOGY'),
  ('11111111-1111-1111-1111-111111111111', 'CT'),
  ('22222222-2222-2222-2222-222222222222', 'EMERGENCY'),
  ('22222222-2222-2222-2222-222222222222', 'ICU'),
  ('22222222-2222-2222-2222-222222222222', 'NEUROLOGY'),
  ('22222222-2222-2222-2222-222222222222', 'CT'),
  ('33333333-3333-3333-3333-333333333333', 'EMERGENCY'),
  ('33333333-3333-3333-3333-333333333333', 'ICU'),
  ('33333333-3333-3333-3333-333333333333', 'NEUROLOGY'),
  ('33333333-3333-3333-3333-333333333333', 'CT')
on conflict do nothing;

-- ---------------------------------------------------------------------
-- Resource definitions
-- ---------------------------------------------------------------------

insert into hospital_resources (hospital_id, resource_type, measurement_type, total_count_optional) values
  ('11111111-1111-1111-1111-111111111111', 'ICU', 'COUNT', 10),
  ('11111111-1111-1111-1111-111111111111', 'NEUROLOGY_SPECIALIST', 'PERSONNEL_AVAILABILITY', null),
  ('11111111-1111-1111-1111-111111111111', 'CT', 'BINARY_SERVICE', null),
  ('22222222-2222-2222-2222-222222222222', 'ICU', 'COUNT', 8),
  ('22222222-2222-2222-2222-222222222222', 'NEUROLOGY_SPECIALIST', 'PERSONNEL_AVAILABILITY', null),
  ('22222222-2222-2222-2222-222222222222', 'CT', 'BINARY_SERVICE', null),
  ('33333333-3333-3333-3333-333333333333', 'ICU', 'COUNT', 6),
  ('33333333-3333-3333-3333-333333333333', 'NEUROLOGY_SPECIALIST', 'PERSONNEL_AVAILABILITY', null),
  ('33333333-3333-3333-3333-333333333333', 'CT', 'BINARY_SERVICE', null)
on conflict do nothing;

-- ---------------------------------------------------------------------
-- Initial hospital_state — matches section 28 exactly:
--   Hospital A  ICU available = 2
--   Hospital B  ICU available = 0
--   Hospital C  ICU available = 1
-- Applied through the same function the simulator uses (step 2.9),
-- so the state-event history is populated identically to a live run.
-- ---------------------------------------------------------------------

select apply_hospital_state_update(
  '11111111-1111-1111-1111-111111111111', 'ICU', 'COUNT', 'AVAILABLE', 2, 10, 'SIMULATOR', 'seed-a-icu-1'
);
select apply_hospital_state_update(
  '22222222-2222-2222-2222-222222222222', 'ICU', 'COUNT', 'UNAVAILABLE', 0, 8, 'SIMULATOR', 'seed-b-icu-1'
);
select apply_hospital_state_update(
  '33333333-3333-3333-3333-333333333333', 'ICU', 'COUNT', 'AVAILABLE', 1, 6, 'SIMULATOR', 'seed-c-icu-1'
);

select apply_hospital_state_update(
  '11111111-1111-1111-1111-111111111111', 'NEUROLOGY_SPECIALIST', 'PERSONNEL_AVAILABILITY', 'AVAILABLE', null, null, 'SIMULATOR', 'seed-a-neuro-1'
);
select apply_hospital_state_update(
  '22222222-2222-2222-2222-222222222222', 'NEUROLOGY_SPECIALIST', 'PERSONNEL_AVAILABILITY', 'ON_CALL', null, null, 'SIMULATOR', 'seed-b-neuro-1'
);
select apply_hospital_state_update(
  '33333333-3333-3333-3333-333333333333', 'NEUROLOGY_SPECIALIST', 'PERSONNEL_AVAILABILITY', 'AVAILABLE', null, null, 'SIMULATOR', 'seed-c-neuro-1'
);

select apply_hospital_state_update(
  '11111111-1111-1111-1111-111111111111', 'CT', 'BINARY_SERVICE', 'OPERATIONAL', null, null, 'SIMULATOR', 'seed-a-ct-1'
);
select apply_hospital_state_update(
  '22222222-2222-2222-2222-222222222222', 'CT', 'BINARY_SERVICE', 'OPERATIONAL', null, null, 'SIMULATOR', 'seed-b-ct-1'
);
select apply_hospital_state_update(
  '33333333-3333-3333-3333-333333333333', 'CT', 'BINARY_SERVICE', 'OPERATIONAL', null, null, 'SIMULATOR', 'seed-c-ct-1'
);

-- ---------------------------------------------------------------------
-- One demo patient, ready to be walked through Stage 1 -> Stage 2
-- ---------------------------------------------------------------------

insert into patients (id, display_name, age, sex) values
  ('99999999-9999-9999-9999-999999999999', 'Demo Patient', 54, 'M')
on conflict (id) do nothing;
