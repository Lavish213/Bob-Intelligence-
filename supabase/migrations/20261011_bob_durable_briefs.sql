BEGIN;

ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS call_brief jsonb;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS call_brief_generated_at timestamptz;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS prior_boxes jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS ownership_denied boolean NOT NULL DEFAULT false;
CREATE UNIQUE INDEX IF NOT EXISTS bob_intel_packet_binding ON public.intel_packets (tenant_id, lead_id);

CREATE TABLE public.bob_brief_jobs (
    lead_id uuid PRIMARY KEY REFERENCES public.leads(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL,
    lease_token uuid,
    leased_until timestamptz,
    source_fingerprint text,
    next_due_at timestamptz NOT NULL DEFAULT now(),
    failures integer NOT NULL DEFAULT 0,
    last_error text,
    quarantined boolean NOT NULL DEFAULT false
);
CREATE INDEX bob_brief_jobs_due ON public.bob_brief_jobs (tenant_id, next_due_at);

CREATE TABLE public.bob_decisions (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    brief jsonb NOT NULL,
    decision jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.bob_outbox (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    payload jsonb NOT NULL,
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'delivered', 'dead')),
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_token uuid,
    leased_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX bob_outbox_due ON public.bob_outbox (tenant_id, state, available_at);

ALTER TABLE public.bob_brief_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bob_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bob_outbox ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bob_brief_jobs, public.bob_decisions, public.bob_outbox FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.bob_brief_jobs, public.bob_decisions, public.bob_outbox TO service_role;

CREATE FUNCTION public.bob_source_snapshot(p_tenant_id uuid, p_lead_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT jsonb_build_object('lead', to_jsonb(l) - 'call_brief' - 'call_brief_generated_at', 'property', coalesce(to_jsonb(p), '{}'::jsonb), 'packet', coalesce(to_jsonb(i), '{}'::jsonb))
    FROM public.leads l
    LEFT JOIN public.properties p ON p.id = l.property_id AND p.tenant_id = l.tenant_id
    LEFT JOIN public.intel_packets i ON i.lead_id = l.id AND i.tenant_id = l.tenant_id
    WHERE l.id = p_lead_id AND l.tenant_id = p_tenant_id
$$;

CREATE FUNCTION public.bob_claim_brief_jobs(p_tenant_id uuid, p_batch_size integer DEFAULT 20, p_lease_seconds integer DEFAULT 120, p_refresh_hours integer DEFAULT 24)
RETURNS TABLE(lead_id uuid, lease_token uuid, source_fingerprint text, snapshot jsonb)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    candidate record;
    snap jsonb;
    token uuid;
BEGIN
    IF p_batch_size NOT BETWEEN 1 AND 100 OR p_lease_seconds NOT BETWEEN 30 AND 600 OR p_refresh_hours NOT BETWEEN 1 AND 168 THEN
        RAISE EXCEPTION 'Invalid worker limits';
    END IF;
    INSERT INTO public.bob_brief_jobs (lead_id, tenant_id)
    SELECT l.id, l.tenant_id FROM public.leads l
    JOIN public.properties p ON p.id = l.property_id AND p.tenant_id = l.tenant_id
    WHERE l.tenant_id = p_tenant_id AND l.opted_out IS FALSE AND l.dnc_blocked IS FALSE
        AND lower(l.stage) NOT IN ('dead', 'closed') AND p.distress_score >= 50
        AND NOT EXISTS (SELECT 1 FROM public.bob_brief_jobs j WHERE j.lead_id = l.id)
    ORDER BY p.distress_score DESC, l.id LIMIT 1000
    ON CONFLICT DO NOTHING;

    FOR candidate IN
        SELECT j.lead_id FROM public.bob_brief_jobs j
        JOIN public.leads l ON l.id = j.lead_id AND l.tenant_id = j.tenant_id
        JOIN public.properties p ON p.id = l.property_id AND p.tenant_id = l.tenant_id
        WHERE j.tenant_id = p_tenant_id AND NOT j.quarantined
            AND (j.leased_until IS NULL OR j.leased_until <= now())
            AND l.opted_out IS FALSE AND l.dnc_blocked IS FALSE
            AND lower(l.stage) NOT IN ('dead', 'closed') AND p.distress_score >= 50
            AND (j.next_due_at <= now() OR (j.failures = 0 AND j.source_fingerprint IS DISTINCT FROM md5(public.bob_source_snapshot(p_tenant_id, j.lead_id)::text)))
        ORDER BY j.next_due_at, p.distress_score DESC, j.lead_id
        LIMIT p_batch_size FOR UPDATE OF j SKIP LOCKED
    LOOP
        snap := public.bob_source_snapshot(p_tenant_id, candidate.lead_id);
        token := gen_random_uuid();
        UPDATE public.bob_brief_jobs j SET lease_token = token, leased_until = now() + make_interval(secs => p_lease_seconds), source_fingerprint = md5(snap::text)
        WHERE j.lead_id = candidate.lead_id;
        RETURN QUERY SELECT candidate.lead_id, token, md5(snap::text), snap;
    END LOOP;
END $$;

CREATE FUNCTION public.bob_complete_brief_job(p_tenant_id uuid, p_lead_id uuid, p_token uuid, p_brief jsonb, p_decision jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    job public.bob_brief_jobs%ROWTYPE;
    expires timestamptz;
BEGIN
    SELECT * INTO job FROM public.bob_brief_jobs j WHERE j.lead_id = p_lead_id AND j.tenant_id = p_tenant_id FOR UPDATE;
    IF NOT FOUND OR p_token IS NULL OR job.lease_token IS DISTINCT FROM p_token OR job.leased_until <= now() THEN RETURN false; END IF;
    PERFORM 1 FROM public.leads l WHERE l.id = p_lead_id AND l.tenant_id = p_tenant_id FOR UPDATE;
    PERFORM 1 FROM public.properties p JOIN public.leads l ON l.property_id = p.id WHERE l.id = p_lead_id AND p.tenant_id = p_tenant_id FOR SHARE OF p;
    PERFORM 1 FROM public.intel_packets i WHERE i.lead_id = p_lead_id AND i.tenant_id = p_tenant_id FOR SHARE;
    IF job.source_fingerprint IS DISTINCT FROM md5(public.bob_source_snapshot(p_tenant_id, p_lead_id)::text) THEN RETURN false; END IF;
    IF p_brief->>'lead_id' IS DISTINCT FROM p_lead_id::text OR p_brief->>'schema_version' IS DISTINCT FROM '2.0'
       OR p_brief->>'ready_for_call' IS DISTINCT FROM 'false' THEN RAISE EXCEPTION 'Invalid brief binding or authority'; END IF;
    expires := (p_brief->>'expires_at')::timestamptz;
    IF expires IS NULL OR expires <= now() OR expires > now() + interval '168 hours' THEN RAISE EXCEPTION 'Invalid brief expiry'; END IF;
    UPDATE public.leads SET call_brief = p_brief, call_brief_generated_at = now() WHERE id = p_lead_id AND tenant_id = p_tenant_id;
    INSERT INTO public.bob_decisions (id, tenant_id, lead_id, brief, decision) VALUES (p_token, p_tenant_id, p_lead_id, p_brief, p_decision);
    INSERT INTO public.bob_outbox (id, tenant_id, payload) VALUES (p_token, p_tenant_id, jsonb_build_object('event_id', p_token, 'schema_version', '2.0', 'event_type', 'call_brief_created', 'lead_id', p_lead_id, 'tenant_id', p_tenant_id, 'phase', p_brief->>'phase', 'missing_box', p_brief->>'missing_box', 'occurred_at', now()));
    UPDATE public.bob_brief_jobs SET lease_token = NULL, leased_until = NULL, failures = 0, last_error = NULL, next_due_at = expires WHERE lead_id = p_lead_id;
    RETURN true;
END $$;

CREATE FUNCTION public.bob_fail_brief_job(p_tenant_id uuid, p_lead_id uuid, p_token uuid, p_reason text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    changed integer;
BEGIN
    UPDATE public.bob_brief_jobs SET failures = failures + 1, last_error = left(p_reason, 200), quarantined = failures + 1 >= 5,
        next_due_at = now() + make_interval(mins => least(60, (2 ^ least(failures, 5))::integer)), lease_token = NULL, leased_until = NULL
    WHERE lead_id = p_lead_id AND tenant_id = p_tenant_id AND lease_token = p_token AND leased_until > now();
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END $$;

CREATE FUNCTION public.bob_claim_events(p_tenant_id uuid, p_batch_size integer DEFAULT 20)
RETURNS SETOF public.bob_outbox LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF p_batch_size NOT BETWEEN 1 AND 100 THEN RAISE EXCEPTION 'Invalid batch size'; END IF;
    RETURN QUERY WITH claimed AS (
        SELECT id FROM public.bob_outbox WHERE tenant_id = p_tenant_id AND state = 'pending' AND available_at <= now()
            AND (leased_until IS NULL OR leased_until <= now()) ORDER BY available_at, id LIMIT p_batch_size FOR UPDATE SKIP LOCKED
    ) UPDATE public.bob_outbox o SET lease_token = gen_random_uuid(), leased_until = now() + interval '120 seconds', attempts = attempts + 1
      FROM claimed c WHERE o.id = c.id RETURNING o.*;
END $$;

CREATE FUNCTION public.bob_finish_event(p_tenant_id uuid, p_event_id uuid, p_token uuid, p_accepted boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    changed integer;
BEGIN
    UPDATE public.bob_outbox SET state = CASE WHEN p_accepted THEN 'delivered' WHEN attempts >= 10 THEN 'dead' ELSE 'pending' END,
        available_at = now() + make_interval(mins => least(60, (2 ^ least(attempts, 5))::integer)), lease_token = NULL, leased_until = NULL
    WHERE id = p_event_id AND tenant_id = p_tenant_id AND lease_token = p_token AND leased_until > now();
    GET DIAGNOSTICS changed = ROW_COUNT;
    RETURN changed = 1;
END $$;

CREATE FUNCTION public.bob_record_call_facts(p_tenant_id uuid, p_lead_id uuid, p_call_sid text, p_facts jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    existing jsonb;
    merged jsonb;
    item record;
    observed timestamptz;
BEGIN
    IF p_call_sid IS NULL OR length(p_call_sid) < 1 OR length(p_call_sid) > 200 OR jsonb_typeof(p_facts) IS DISTINCT FROM 'object' THEN RETURN false; END IF;
    SELECT prior_boxes INTO existing FROM public.leads WHERE id = p_lead_id AND tenant_id = p_tenant_id FOR UPDATE;
    IF NOT FOUND THEN RETURN false; END IF;
    merged := coalesce(existing, '{}'::jsonb);
    FOR item IN SELECT key, value FROM jsonb_each(p_facts) LOOP
        IF item.key NOT IN ('right_person', 'property_confirmed', 'occupancy', 'condition', 'timeline', 'motivation', 'next_step')
            OR jsonb_typeof(item.value->'confirmed') IS DISTINCT FROM 'boolean'
            OR item.value->>'source' IS DISTINCT FROM 'transcript_verified'
            OR item.value->>'call_sid' IS DISTINCT FROM p_call_sid THEN RAISE EXCEPTION 'Invalid fact provenance'; END IF;
        observed := (item.value->>'verified_at')::timestamptz;
        IF observed IS NULL OR observed > now() + interval '1 minute' OR observed < now() - interval '24 hours' THEN RAISE EXCEPTION 'Invalid fact time'; END IF;
        IF merged->item.key->>'verified_at' IS NULL OR observed >= (merged->item.key->>'verified_at')::timestamptz THEN
            merged := jsonb_set(merged, ARRAY[item.key], item.value, true);
        END IF;
    END LOOP;
    UPDATE public.leads SET prior_boxes = merged,
        ownership_denied = CASE WHEN merged->'right_person'->>'confirmed' IS NOT NULL THEN NOT (merged->'right_person'->>'confirmed')::boolean ELSE ownership_denied END,
        updated_at = now()
    WHERE id = p_lead_id AND tenant_id = p_tenant_id;
    RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.bob_record_call_facts(uuid, uuid, text, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.bob_record_call_facts(uuid, uuid, text, jsonb) TO service_role;

REVOKE ALL ON FUNCTION public.bob_source_snapshot(uuid, uuid), public.bob_claim_brief_jobs(uuid, integer, integer, integer), public.bob_complete_brief_job(uuid, uuid, uuid, jsonb, jsonb), public.bob_fail_brief_job(uuid, uuid, uuid, text), public.bob_claim_events(uuid, integer), public.bob_finish_event(uuid, uuid, uuid, boolean) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.bob_source_snapshot(uuid, uuid), public.bob_claim_brief_jobs(uuid, integer, integer, integer), public.bob_complete_brief_job(uuid, uuid, uuid, jsonb, jsonb), public.bob_fail_brief_job(uuid, uuid, uuid, text), public.bob_claim_events(uuid, integer), public.bob_finish_event(uuid, uuid, uuid, boolean) TO service_role;

COMMIT;
