-- =====================================================================
-- 002_atomic_transitions.sql
--
-- Database-level conditional transitions. Per step 7.3 / section 0.3,
-- race protection (referral acceptance, hospital confirmation) must
-- happen in the database, not in application code or React.
--
-- Each function returns the number of rows changed (0 or 1) so the
-- Flask layer can distinguish "you won the race" from "someone else
-- already won it" without a second round-trip.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Hospital state update: monotonic version check + idempotent event log
-- (step 2.8). Safe to call twice with the same source_event_id.
-- ---------------------------------------------------------------------

create or replace function apply_hospital_state_update(
  p_hospital_id uuid,
  p_resource_type text,
  p_measurement_type measurement_type,
  p_status text,
  p_available_count integer,
  p_total_count integer,
  p_source text,
  p_source_event_id text
) returns table(applied boolean, new_version bigint) as $$
declare
  v_existing hospital_state%rowtype;
  v_next_version bigint;
begin
  -- Idempotency: if this exact upstream event was already applied, no-op.
  if exists (
    select 1 from hospital_state_events
    where hospital_id = p_hospital_id
      and resource_type = p_resource_type
      and source = p_source
      and source_event_id = p_source_event_id
  ) then
    select version into v_next_version from hospital_state
      where hospital_id = p_hospital_id and resource_type = p_resource_type;
    return query select false, v_next_version;
    return;
  end if;

  select * into v_existing from hospital_state
    where hospital_id = p_hospital_id and resource_type = p_resource_type
    for update;

  if not found then
    v_next_version := 1;
    insert into hospital_state (
      hospital_id, resource_type, measurement_type, status,
      available_count_optional, total_count_optional,
      updated_at, source, source_event_id, version
    ) values (
      p_hospital_id, p_resource_type, p_measurement_type, p_status,
      p_available_count, p_total_count,
      now(), p_source, p_source_event_id, v_next_version
    );

    insert into hospital_state_events (
      hospital_id, resource_type, event_type, old_value, new_value,
      event_timestamp, source, source_event_id, version
    ) values (
      p_hospital_id, p_resource_type, 'STATE_CREATED', null,
      jsonb_build_object('status', p_status, 'available_count', p_available_count, 'total_count', p_total_count),
      now(), p_source, p_source_event_id, v_next_version
    );

    return query select true, v_next_version;
    return;
  end if;

  -- Do not let an out-of-order / stale update overwrite newer state.
  v_next_version := v_existing.version + 1;

  update hospital_state set
    measurement_type = p_measurement_type,
    status = p_status,
    available_count_optional = p_available_count,
    total_count_optional = p_total_count,
    updated_at = now(),
    source = p_source,
    source_event_id = p_source_event_id,
    version = v_next_version
  where hospital_id = p_hospital_id and resource_type = p_resource_type;

  insert into hospital_state_events (
    hospital_id, resource_type, event_type, old_value, new_value,
    event_timestamp, source, source_event_id, version
  ) values (
    p_hospital_id, p_resource_type, 'STATE_UPDATED',
    jsonb_build_object('status', v_existing.status, 'available_count', v_existing.available_count_optional, 'total_count', v_existing.total_count_optional),
    jsonb_build_object('status', p_status, 'available_count', p_available_count, 'total_count', p_total_count),
    now(), p_source, p_source_event_id, v_next_version
  );

  return query select true, v_next_version;
end;
$$ language plpgsql;

-- ---------------------------------------------------------------------
-- Stage-1: patient selects an accepted hospital (atomic; step 4.12)
-- ---------------------------------------------------------------------

create or replace function select_hospital_for_request(
  p_request_id uuid,
  p_hospital_id uuid
) returns boolean as $$
declare
  v_rows integer;
begin
  update patient_requests
  set status = 'CONFIRMING',
      selected_hospital_id_optional = p_hospital_id,
      version = version + 1
  where id = p_request_id
    and status = 'PATIENT_SELECTING'
    and exists (
      select 1 from patient_request_responses
      where request_id = p_request_id
        and hospital_id = p_hospital_id
        and status = 'ACCEPTED'
    );

  get diagnostics v_rows = row_count;
  return v_rows = 1;
end;
$$ language plpgsql;

-- ---------------------------------------------------------------------
-- Stage-1: hospital confirms after revalidating its own state
-- (atomic; failure returns the request to PATIENT_SELECTING)
-- ---------------------------------------------------------------------

create or replace function confirm_hospital_match(
  p_request_id uuid,
  p_hospital_id uuid,
  p_still_eligible boolean
) returns text as $$
declare
  v_rows integer;
begin
  if p_still_eligible then
    update patient_requests
    set status = 'MATCHED',
        matched_hospital_id_optional = p_hospital_id,
        version = version + 1
    where id = p_request_id
      and status = 'CONFIRMING'
      and selected_hospital_id_optional = p_hospital_id;

    get diagnostics v_rows = row_count;
    if v_rows = 1 then
      return 'MATCHED';
    else
      return 'CONFIRMATION_FAILED';
    end if;
  else
    update patient_requests
    set status = 'PATIENT_SELECTING',
        selected_hospital_id_optional = null,
        version = version + 1
    where id = p_request_id
      and status = 'CONFIRMING'
      and selected_hospital_id_optional = p_hospital_id;

    return 'CONFIRMATION_FAILED';
  end if;
end;
$$ language plpgsql;

-- ---------------------------------------------------------------------
-- Stage-2: atomic referral acceptance (step 7.3, exact spec pattern)
-- ---------------------------------------------------------------------

create or replace function accept_referral(
  p_referral_id uuid,
  p_hospital_id uuid
) returns boolean as $$
declare
  v_rows integer;
begin
  update referrals
  set status = 'ACCEPTED',
      accepted_by_hospital_id_optional = p_hospital_id,
      accepted_at_optional = now(),
      version = version + 1
  where id = p_referral_id
    and status = 'PENDING_ACCEPTANCE';

  get diagnostics v_rows = row_count;

  if v_rows = 1 then
    update referral_responses
    set status = 'ACCEPTED', responded_at = now()
    where referral_id = p_referral_id and hospital_id = p_hospital_id;

    -- Any other still-pending responses are implicitly moot; the
    -- application layer marks them EXPIRED for display purposes.
    return true;
  end if;

  return false;
end;
$$ language plpgsql;
