# National Patient Navigation & Referral Coordination Network — Prototype

A two-stage patient-to-hospital and hospital-to-hospital coordination
platform, built from `docs/PROJECT_SPEC.md` (the original build spec).
This build pass implements the **end-to-end demo path** (spec section
45 / the core demo scenario in section 28) with real
service-integration code — Supabase Postgres, a Hugging Face
medical-triage transformer, and an OSRM routing client — rather than
mocked stand-ins. See `docs/PROTOTYPE_LIMITATIONS.md` for exactly what
is and isn't wired up, and `docs/DECISIONS.md` for judgment calls made
along the way.

**This is prototype software using entirely synthetic data.** It does
not diagnose patients, reserve real hospital beds, or represent any
real hospital's actual capacity. See section 6 of the spec ("Never
collapse these into one ambiguous concept... Do not fabricate
real-time capacity figures for real hospitals").

## Repository layout

```
frontend/    React + Vite + Leaflet — patient, hospital, and admin UIs
backend/     Flask API — triage, referral engine, routing, state machines
database/    Supabase Postgres migrations + demo seed data
docs/        Data model, API reference, state machines, decisions, limitations
scripts/     Demo state reset script
```

## 1. Set up Supabase

1. Create a project at supabase.com.
2. In the SQL editor (or via `supabase db push` with the CLI), run, in
   order:
   - `database/migrations/001_init_schema.sql`
   - `database/migrations/002_atomic_transitions.sql`
   - `database/migrations/003_rls_policies.sql`
   - `database/seed/demo_seed.sql`
3. Copy your project's connection pooling URI (service role) and
   project URL/anon key — you'll need both.

**Already have a project running an earlier version of this schema?**
Re-run `001_init_schema.sql` — it's written with `create table` (not
`if not exists`) for new tables like `emergency_dispatches`, but the
`referrals` table changed shape (new nullable/optional columns). If
your project already has the old `referrals` table, either drop and
re-create it from a fresh project, or apply this diff manually:
```sql
alter table referrals alter column referring_hospital_id drop not null;
alter table referrals add column if not exists initiated_by text not null default 'PATIENT';
alter table referrals add column if not exists referring_doctor_name text;
alter table referrals add column if not exists origin_lat double precision;
alter table referrals add column if not exists origin_lon double precision;
alter table referrals add column if not exists source_document_note text;
```

## 2. Configure the backend

```bash
cd backend
cp .env.example .env
# fill in SUPABASE_DB_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
# fill in HF_API_TOKEN — required even for local loading, since
# google/medgemma-4b-it is a GATED model: accept the license at
# https://huggingface.co/google/medgemma-4b-it with the same account
# first, or model loading will fail with 401/403
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Check readiness before moving on:

```bash
curl http://localhost:8000/ready
```

`ready: false` most commonly means the triage model hasn't finished
loading yet (local mode) or `SUPABASE_DB_URL` is wrong.

## 3. Configure the frontend

```bash
cd frontend
cp .env.example .env
# fill in VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY (client-safe anon
# key only — never the service-role key) and VITE_DEMO_ADMIN_TOKEN
# (must match backend's DEMO_ADMIN_TOKEN)
npm install
npm run dev
```

Open http://localhost:5173.

## 4. Run the tests

```bash
cd backend
pip install -r requirements.txt   # if not already
pytest
```

These are pure-logic unit tests (referral engine eligibility/ranking,
state-machine transitions per step 22.1/22.2) — no live Supabase/HF/
OSRM connection required.

## 5. Walk through the demo

Open three browser windows/profiles (section 30 — don't reuse one tab
with manually changing roles) and pick a role from the landing page in
each: **Patient**, **Hospital**, **Admin**.

### Emergency path

1. **Patient** → the red **Emergency — Dispatch Ambulance** button is
   visible on every patient screen. Tap it: no questions asked, the
   nearest hospital with emergency capability is dispatched
   immediately and you land on `/patient/emergency-status`.

### Stage-1 (assessment → hospital match) path

1. **Patient**: create a patient, run an assessment (try "sudden
   weakness on one side, difficulty speaking" + "Suspected stroke
   symptoms"), submit the request.
2. **Hospital**: pick a demo hospital in range (Stage-1 Requests tab),
   accept the incoming request, then (after the patient selects you)
   confirm the match.
3. **Patient**: select the accepted hospital, watch it move to
   MATCHED, then `/patient/journey` to see the status stepper.
4. **Hospital** (Active Patients tab): mark en route → arrived → begin
   care.

### Stage-2 (patient-initiated referral) path

5. **Patient** → **Get a Referral**: either scan a photo of a referral
   letter (MedGemma extracts the fields — review/edit them) or switch
   to "Enter manually," pick required capabilities (try `ICU`), and
   submit. This runs the referral engine and shows ranked/rejected
   hospitals.
6. **Admin** (`/admin/simulator`): enter the demo admin token, then hit
   **Run scenario** to drive Hospital A's ICU from 2 → 1 → 0 live —
   this is the exact section 28 sequence. Watch the referral's ranked
   list or `/admin/network` update as Hospital A drops out of the
   eligible set and Hospital C takes over #1.
7. **Hospital** (Incoming Referrals tab): pick the newly-top-ranked
   hospital, view the incoming referral, accept it, then start the
   transfer.
8. **Hospital** (same or a second window acting as the receiving
   hospital): mark received, fill in and complete the handoff.
9. **Patient**: `/patient/journey` now shows `COMPLETED`.

This exercises: database as source of truth, the journey/Stage-1/
Stage-2/transfer state machines, Supabase Realtime, hard-constraint
eligibility, deterministic ranking with explanations, atomic
acceptance, patient-initiated referrals (scanned or manual), and the
emergency-dispatch path — see `docs/DECISIONS.md` for what changed
and why.

## Prototype data rule

Everything seeded — Hospital A/B/C, their capabilities, and their
operational state — is synthetic (`hospitals.is_synthetic = true`).
Never present these figures as real hospital capacity (section 23).
