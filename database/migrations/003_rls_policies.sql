-- =====================================================================
-- 003_rls_policies.sql
--
-- Row Level Security. Backend writes generally go through the Flask
-- service-role connection (which bypasses RLS by design — see
-- backend/app/services/db.py), so these policies primarily govern:
--   - direct-from-frontend reads (Supabase client / Realtime),
--   - any direct-from-frontend writes explicitly allowed (e.g. hospital
--     staff updating only their own hospital's state).
--
-- Roles (section 19): PATIENT, DOCTOR, HOSPITAL_STAFF, NETWORK_ADMIN
-- =====================================================================

alter table app_users enable row level security;
alter table hospitals enable row level security;
alter table hospital_capabilities enable row level security;
alter table hospital_resources enable row level security;
alter table hospital_state enable row level security;
alter table hospital_state_events enable row level security;
alter table patients enable row level security;
alter table assessments enable row level security;
alter table journeys enable row level security;
alter table patient_requests enable row level security;
alter table patient_request_responses enable row level security;
alter table referrals enable row level security;
alter table referral_requirements enable row level security;
alter table referral_responses enable row level security;
alter table referral_evaluations enable row level security;
alter table transfers enable row level security;
alter table handoffs enable row level security;
alter table emergency_dispatches enable row level security;
alter table audit_events enable row level security;

-- Helper: current caller's app role / hospital, read once per policy.
create or replace function current_app_role() returns user_role as $$
  select role from app_users where id = auth.uid();
$$ language sql stable;

create or replace function current_app_hospital() returns uuid as $$
  select hospital_id from app_users where id = auth.uid();
$$ language sql stable;

-- ---------------------------------------------------------------------
-- app_users: users can read their own row; admin reads all.
-- ---------------------------------------------------------------------

create policy app_users_self_read on app_users
  for select using (id = auth.uid() or current_app_role() = 'NETWORK_ADMIN');

-- ---------------------------------------------------------------------
-- Hospitals / capabilities: public read (needed for candidate search,
-- map view). Network data is synthetic prototype data (section 6.6),
-- so open read is acceptable here.
-- ---------------------------------------------------------------------

create policy hospitals_public_read on hospitals for select using (true);
create policy hospital_capabilities_public_read on hospital_capabilities for select using (true);
create policy hospital_resources_public_read on hospital_resources for select using (true);

-- ---------------------------------------------------------------------
-- Hospital state: readable by anyone with network visibility; writable
-- only by that hospital's own staff or the demo/admin simulator
-- (section 41V — no generic "update any hospital state" API).
-- ---------------------------------------------------------------------

create policy hospital_state_read on hospital_state for select using (true);

create policy hospital_state_own_hospital_write on hospital_state
  for update using (
    current_app_role() = 'NETWORK_ADMIN'
    or (current_app_role() = 'HOSPITAL_STAFF' and current_app_hospital() = hospital_id)
  );

create policy hospital_state_events_read on hospital_state_events for select using (true);

-- ---------------------------------------------------------------------
-- Patients: readable/writable by the patient's own requester, or by
-- staff at a hospital currently on that patient's active journey.
-- ---------------------------------------------------------------------

create policy patients_requester_read on patients
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or exists (
      select 1 from patient_requests pr
      where pr.patient_id = patients.id
        and pr.requester_user_id_optional = auth.uid()
    )
    or exists (
      select 1 from journeys j
      where j.patient_id = patients.id
        and (j.stage1_hospital_id = current_app_hospital() or j.stage2_hospital_id = current_app_hospital())
    )
  );

create policy assessments_owner_read on assessments
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or exists (
      select 1 from patient_requests pr
      where pr.patient_id = assessments.patient_id
        and pr.requester_user_id_optional = auth.uid()
    )
  );

-- ---------------------------------------------------------------------
-- Journeys: visible to the requester and to any hospital named on it.
-- ---------------------------------------------------------------------

create policy journeys_participant_read on journeys
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or stage1_hospital_id = current_app_hospital()
    or stage2_hospital_id = current_app_hospital()
    or exists (
      select 1 from patient_requests pr
      where pr.id = journeys.stage1_request_id
        and pr.requester_user_id_optional = auth.uid()
    )
  );

-- ---------------------------------------------------------------------
-- Stage-1 requests / responses
-- ---------------------------------------------------------------------

create policy patient_requests_owner_read on patient_requests
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or requester_user_id_optional = auth.uid()
    or exists (
      select 1 from patient_request_responses prr
      where prr.request_id = patient_requests.id
        and prr.hospital_id = current_app_hospital()
    )
  );

-- Patient location note: exact coordinates on patient_requests are
-- only exposed via this same policy to hospitals that already have a
-- response row for the request — i.e. hospitals in the candidate set.
-- The API layer additionally strips lat/lon from the *broadcast* list
-- view before the hospital has responded (step 4.8); full exposure
-- through this table read is acceptable prototype behavior for a
-- hospital already inside the workflow.

create policy patient_request_responses_participant_read on patient_request_responses
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or hospital_id = current_app_hospital()
    or exists (
      select 1 from patient_requests pr
      where pr.id = patient_request_responses.request_id
        and pr.requester_user_id_optional = auth.uid()
    )
  );

create policy patient_request_responses_own_hospital_write on patient_request_responses
  for update using (
    current_app_role() = 'HOSPITAL_STAFF' and hospital_id = current_app_hospital()
  );

-- ---------------------------------------------------------------------
-- Stage-2 referrals / responses / evaluations
-- ---------------------------------------------------------------------

create policy referrals_participant_read on referrals
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or referring_hospital_id = current_app_hospital()
    or accepted_by_hospital_id_optional = current_app_hospital()
    or exists (
      select 1 from referral_responses rr
      where rr.referral_id = referrals.id and rr.hospital_id = current_app_hospital()
    )
  );

create policy referral_requirements_participant_read on referral_requirements
  for select using (
    exists (
      select 1 from referrals r
      where r.id = referral_requirements.referral_id
        and (
          current_app_role() = 'NETWORK_ADMIN'
          or r.referring_hospital_id = current_app_hospital()
          or exists (
            select 1 from referral_responses rr
            where rr.referral_id = r.id and rr.hospital_id = current_app_hospital()
          )
        )
    )
  );

create policy referral_responses_participant_read on referral_responses
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or hospital_id = current_app_hospital()
    or exists (
      select 1 from referrals r
      where r.id = referral_responses.referral_id
        and r.referring_hospital_id = current_app_hospital()
    )
  );

create policy referral_responses_own_hospital_write on referral_responses
  for update using (
    current_app_role() = 'HOSPITAL_STAFF' and hospital_id = current_app_hospital()
  );

create policy referral_evaluations_participant_read on referral_evaluations
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or exists (
      select 1 from referrals r
      where r.id = referral_evaluations.referral_id
        and r.referring_hospital_id = current_app_hospital()
    )
  );

-- ---------------------------------------------------------------------
-- Transfers / handoffs
-- ---------------------------------------------------------------------

create policy transfers_participant_read on transfers
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or exists (
      select 1 from referrals r
      where r.id = transfers.referral_id
        and (r.referring_hospital_id = current_app_hospital() or r.accepted_by_hospital_id_optional = current_app_hospital())
    )
  );

create policy handoffs_participant_read on handoffs
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or exists (
      select 1 from referrals r
      where r.id = handoffs.referral_id
        and (r.referring_hospital_id = current_app_hospital() or r.accepted_by_hospital_id_optional = current_app_hospital())
    )
  );

-- ---------------------------------------------------------------------
-- Emergency dispatch: visible to the requester and the dispatched
-- hospital; admin sees all (mirrors the urgency of the feature itself
-- — no hospital-side accept/decline gate on read access).
-- ---------------------------------------------------------------------

create policy emergency_dispatches_participant_read on emergency_dispatches
  for select using (
    current_app_role() = 'NETWORK_ADMIN'
    or dispatched_hospital_id = current_app_hospital()
    or exists (
      select 1 from patients p where p.id = emergency_dispatches.patient_id
    )
  );

-- ---------------------------------------------------------------------
-- Audit events: admin only (demo/debug interface, section 41U)
-- ---------------------------------------------------------------------

create policy audit_events_admin_read on audit_events
  for select using (current_app_role() = 'NETWORK_ADMIN');
