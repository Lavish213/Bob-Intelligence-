CREATE INDEX IF NOT EXISTS bob_decisions_latest_per_lead
    ON public.bob_decisions (tenant_id, lead_id, created_at DESC);

CREATE OR REPLACE FUNCTION public.bob_opportunity_overview(p_tenant_id uuid, p_limit integer DEFAULT 25)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
WITH latest AS (
    SELECT DISTINCT ON (d.lead_id)
        d.lead_id,
        d.created_at,
        d.brief -> 'evidence' -> 'opportunity' AS opportunity,
        d.brief -> 'evidence' -> 'valuation' AS valuation
    FROM bob_decisions d
    WHERE d.tenant_id = p_tenant_id
    ORDER BY d.lead_id, d.created_at DESC
),
graded AS (
    SELECT
        l.lead_id,
        l.created_at,
        l.opportunity,
        coalesce(l.opportunity ->> 'readiness', 'UNGRADED') AS readiness,
        coalesce(l.opportunity ->> 'grade', 'ungraded') AS grade,
        coalesce(l.opportunity ->> 'evidence_confidence', 'unknown') AS evidence_confidence,
        l.opportunity ->> 'next_action' AS next_action,
        l.opportunity ->> 'lockout_class' AS lockout_class,
        nullif(l.opportunity -> 'economics' ->> 'arv_point_cents', '')::bigint AS arv_point_cents,
        nullif(l.opportunity -> 'economics' ->> 'purchase_limit_cents', '')::bigint AS purchase_limit_cents,
        nullif(l.opportunity -> 'economics' ->> 'asking_price_cents', '')::bigint AS asking_price_cents,
        nullif(l.opportunity -> 'economics' ->> 'headroom_cents', '')::bigint AS headroom_cents,
        nullif(l.opportunity -> 'economics' ->> 'headroom_bps', '')::bigint AS headroom_bps,
        coalesce(l.opportunity -> 'economics' ->> 'state', 'unknown') AS economics_state,
        coalesce(jsonb_array_length(l.opportunity -> 'blocked_reasons'), 0) AS blocked_count,
        coalesce(l.valuation ->> 'status', 'absent') AS valuation_status,
        coalesce(nullif(l.valuation ->> 'comparable_count', '')::integer, 0) AS comparable_count
    FROM latest l
    WHERE l.opportunity IS NOT NULL AND jsonb_typeof(l.opportunity) = 'object'
),
enriched AS (
    SELECT g.*, p.address, p.city, p.distress_score
    FROM graded g
    LEFT JOIN leads le ON le.id = g.lead_id AND le.tenant_id = p_tenant_id
    LEFT JOIN properties p ON p.id = le.property_id AND p.tenant_id = p_tenant_id
),
ranked AS (
    SELECT e.*, row_number() OVER (
        PARTITION BY e.readiness
        ORDER BY e.headroom_bps DESC NULLS LAST, e.distress_score DESC NULLS LAST, e.created_at DESC
    ) AS rank_in_readiness
    FROM enriched e
)
SELECT jsonb_build_object(
    'schema_version', 1,
    'generated_at', to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'graded_leads', (SELECT count(*) FROM graded),
    'blocked_leads', (SELECT count(*) FROM graded WHERE blocked_count > 0),
    'economics_unknown_leads', (SELECT count(*) FROM graded WHERE economics_state <> 'known'),
    'by_readiness', coalesce((SELECT jsonb_object_agg(readiness, total) FROM (SELECT readiness, count(*) AS total FROM graded GROUP BY readiness) r), '{}'::jsonb),
    'by_grade', coalesce((SELECT jsonb_object_agg(grade, total) FROM (SELECT grade, count(*) AS total FROM graded GROUP BY grade) r), '{}'::jsonb),
    'by_evidence_confidence', coalesce((SELECT jsonb_object_agg(evidence_confidence, total) FROM (SELECT evidence_confidence, count(*) AS total FROM graded GROUP BY evidence_confidence) r), '{}'::jsonb),
    'by_lockout_class', coalesce((SELECT jsonb_object_agg(lockout_class, total) FROM (SELECT lockout_class, count(*) AS total FROM graded WHERE lockout_class IS NOT NULL GROUP BY lockout_class) r), '{}'::jsonb),
    'deals', coalesce((
        SELECT jsonb_agg(jsonb_build_object(
            'lead_id', lead_id,
            'address', address,
            'city', city,
            'distress_score', distress_score,
            'grade', grade,
            'readiness', readiness,
            'evidence_confidence', evidence_confidence,
            'economics_state', economics_state,
            'arv_point_cents', arv_point_cents,
            'asking_price_cents', asking_price_cents,
            'purchase_limit_cents', purchase_limit_cents,
            'headroom_cents', headroom_cents,
            'headroom_bps', headroom_bps,
            'valuation_status', valuation_status,
            'comparable_count', comparable_count,
            'blocked_count', blocked_count,
            'lockout_class', lockout_class,
            'next_action', next_action,
            'graded_at', to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"')
        ) ORDER BY
            CASE readiness WHEN 'HOT_BUY' THEN 0 WHEN 'WATCH_LIST' THEN 1 ELSE 2 END,
            headroom_bps DESC NULLS LAST,
            distress_score DESC NULLS LAST)
        FROM ranked
        WHERE rank_in_readiness <= greatest(1, least(coalesce(p_limit, 25), 100))
    ), '[]'::jsonb),
    'authority', jsonb_build_object(
        'quote_authorized', false,
        'offer_authorized', false,
        'grading_basis', 'internal_screening_policy_not_an_appraisal_or_investment_guarantee')
)
$$;

REVOKE ALL ON FUNCTION public.bob_opportunity_overview(uuid, integer) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.bob_opportunity_overview(uuid, integer) TO service_role;
