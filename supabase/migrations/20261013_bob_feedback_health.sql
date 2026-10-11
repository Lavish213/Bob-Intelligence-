BEGIN;
CREATE TABLE public.bob_fact_receipts (
    event_id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL,
    lead_id uuid NOT NULL REFERENCES public.leads(id) ON DELETE CASCADE,
    call_sid text NOT NULL,
    fingerprint text NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.bob_fact_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bob_fact_receipts FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.bob_fact_receipts TO service_role;

CREATE OR REPLACE FUNCTION public.bob_record_call_facts(p_tenant_id uuid, p_lead_id uuid, p_call_sid text, p_facts jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    existing jsonb;
    merged jsonb;
    item record;
    observed timestamptz;
    previous timestamptz;
BEGIN
    IF p_call_sid IS NULL OR length(p_call_sid) NOT BETWEEN 1 AND 200 OR jsonb_typeof(p_facts) IS DISTINCT FROM 'object' OR p_facts = '{}'::jsonb THEN RETURN false; END IF;
    SELECT prior_boxes INTO existing FROM public.leads WHERE id = p_lead_id AND tenant_id = p_tenant_id FOR UPDATE;
    IF NOT FOUND THEN RETURN false; END IF;
    merged := CASE WHEN jsonb_typeof(existing) = 'object' THEN existing ELSE '{}'::jsonb END;
    FOR item IN SELECT key, value FROM jsonb_each(p_facts) LOOP
        IF item.key NOT IN ('right_person', 'property_confirmed', 'occupancy', 'condition', 'timeline', 'motivation', 'next_step')
            OR jsonb_typeof(item.value) IS DISTINCT FROM 'object'
            OR jsonb_typeof(item.value->'confirmed') IS DISTINCT FROM 'boolean'
            OR item.value->>'source' IS DISTINCT FROM 'transcript_verified'
            OR item.value->>'call_sid' IS DISTINCT FROM p_call_sid THEN RAISE EXCEPTION 'Invalid fact provenance'; END IF;
        observed := (item.value->>'verified_at')::timestamptz;
        IF observed IS NULL OR observed > now() + interval '1 minute' OR observed < now() - interval '24 hours' THEN RAISE EXCEPTION 'Invalid fact time'; END IF;
        BEGIN
            previous := (merged->item.key->>'verified_at')::timestamptz;
        EXCEPTION WHEN invalid_datetime_format OR datetime_field_overflow THEN
            previous := NULL;
        END;
        IF previous IS NULL OR observed > previous OR (observed = previous AND item.value->'confirmed' = 'false'::jsonb) THEN
            merged := jsonb_set(merged, ARRAY[item.key], item.value, true);
        END IF;
    END LOOP;
    IF merged IS DISTINCT FROM existing THEN
        UPDATE public.leads SET prior_boxes = merged,
            ownership_denied = CASE WHEN jsonb_typeof(merged->'right_person'->'confirmed') = 'boolean' THEN NOT (merged->'right_person'->>'confirmed')::boolean ELSE ownership_denied END,
            updated_at = clock_timestamp()
        WHERE id = p_lead_id AND tenant_id = p_tenant_id;
    END IF;
    RETURN true;
END $$;

CREATE FUNCTION public.bob_accept_call_facts(p_tenant_id uuid, p_lead_id uuid, p_call_sid text, p_event_id uuid, p_facts jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    receipt public.bob_fact_receipts%ROWTYPE;
    digest text;
    inserted integer;
BEGIN
    IF p_event_id IS NULL THEN RETURN false; END IF;
    PERFORM 1 FROM public.leads WHERE id = p_lead_id AND tenant_id = p_tenant_id FOR UPDATE;
    IF NOT FOUND THEN RETURN false; END IF;
    digest := md5(p_facts::text);
    INSERT INTO public.bob_fact_receipts(event_id, tenant_id, lead_id, call_sid, fingerprint)
        VALUES(p_event_id, p_tenant_id, p_lead_id, p_call_sid, digest) ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS inserted = ROW_COUNT;
    SELECT * INTO receipt FROM public.bob_fact_receipts WHERE event_id = p_event_id;
    IF receipt.tenant_id IS DISTINCT FROM p_tenant_id OR receipt.lead_id IS DISTINCT FROM p_lead_id OR receipt.call_sid IS DISTINCT FROM p_call_sid OR receipt.fingerprint IS DISTINCT FROM digest THEN
        RAISE EXCEPTION 'Fact receipt binding mismatch';
    END IF;
    IF inserted = 0 THEN RETURN true; END IF;
    IF NOT public.bob_record_call_facts(p_tenant_id, p_lead_id, p_call_sid, p_facts) THEN RAISE EXCEPTION 'Fact merge rejected'; END IF;
    RETURN true;
END $$;

CREATE TABLE public.bob_worker_runs (
    tenant_id uuid PRIMARY KEY,
    completed_at timestamptz NOT NULL,
    errors integer NOT NULL,
    processed integer NOT NULL,
    briefs_created integer NOT NULL
);
ALTER TABLE public.bob_worker_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bob_worker_runs FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.bob_worker_runs TO service_role;
CREATE FUNCTION public.bob_report_worker_run(p_tenant_id uuid, p_errors integer, p_processed integer, p_briefs_created integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF p_errors < 0 OR p_processed < 0 OR p_briefs_created < 0 OR p_briefs_created > p_processed THEN RETURN false; END IF;
    INSERT INTO public.bob_worker_runs VALUES(p_tenant_id, clock_timestamp(), p_errors, p_processed, p_briefs_created)
    ON CONFLICT(tenant_id) DO UPDATE SET completed_at = EXCLUDED.completed_at, errors = EXCLUDED.errors, processed = EXCLUDED.processed, briefs_created = EXCLUDED.briefs_created;
    RETURN true;
END $$;
CREATE FUNCTION public.bob_integration_health(p_tenant_id uuid)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT jsonb_build_object(
        'contract_version', '2.1', 'backend', 'REI-AGENT',
        'worker', (SELECT to_jsonb(w) - 'tenant_id' FROM bob_worker_runs w WHERE w.tenant_id = p_tenant_id),
        'quarantined_jobs', (SELECT count(*) FROM bob_brief_jobs WHERE tenant_id = p_tenant_id AND quarantined),
        'pending_events', (SELECT count(*) FROM bob_outbox WHERE tenant_id = p_tenant_id AND state = 'pending'),
        'dead_events', (SELECT count(*) FROM bob_outbox WHERE tenant_id = p_tenant_id AND state = 'dead'),
        'oldest_pending_event_seconds', (SELECT greatest(0, extract(epoch FROM now() - min(created_at))) FROM bob_outbox WHERE tenant_id = p_tenant_id AND state = 'pending'),
        'stale_briefs', (SELECT count(*) FROM leads l JOIN properties p ON p.id = l.property_id AND p.tenant_id = l.tenant_id WHERE l.tenant_id = p_tenant_id AND l.opted_out IS FALSE AND l.dnc_blocked IS FALSE AND lower(l.stage) NOT IN ('dead', 'closed') AND p.distress_score >= 50 AND l.call_brief_generated_at < now() - interval '24 hours'))
$$;
REVOKE ALL ON FUNCTION public.bob_accept_call_facts(uuid, uuid, text, uuid, jsonb), public.bob_report_worker_run(uuid, integer, integer, integer), public.bob_integration_health(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.bob_accept_call_facts(uuid, uuid, text, uuid, jsonb), public.bob_report_worker_run(uuid, integer, integer, integer), public.bob_integration_health(uuid) TO service_role;
CREATE TABLE public.bob_brief_receipts (
    event_id uuid PRIMARY KEY REFERENCES public.bob_decisions(id) ON DELETE CASCADE,
    tenant_id uuid NOT NULL,
    received_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.bob_brief_receipts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.bob_brief_receipts FROM PUBLIC, anon, authenticated;
GRANT ALL ON public.bob_brief_receipts TO service_role;
CREATE FUNCTION public.bob_accept_brief_event(p_tenant_id uuid, p_event_id uuid, p_payload jsonb)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
    IF p_payload->>'event_id' IS DISTINCT FROM p_event_id::text OR p_payload->>'tenant_id' IS DISTINCT FROM p_tenant_id::text THEN RETURN false; END IF;
    PERFORM 1 FROM bob_outbox WHERE id = p_event_id AND tenant_id = p_tenant_id AND payload = p_payload;
    IF NOT FOUND THEN RETURN false; END IF;
    INSERT INTO bob_brief_receipts(event_id, tenant_id) VALUES(p_event_id, p_tenant_id) ON CONFLICT DO NOTHING;
    RETURN true;
END $$;
REVOKE ALL ON FUNCTION public.bob_accept_brief_event(uuid, uuid, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.bob_accept_brief_event(uuid, uuid, jsonb) TO service_role;
COMMIT;
