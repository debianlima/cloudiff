\set ON_ERROR_STOP on
BEGIN;
INSERT INTO cloudiff_v2.nodes(node_id,hostname,role,capabilities,observed_at) VALUES ('00000000-0000-4000-8000-000000000098','sql-test','other','{}','2026-08-20T12:00:00Z') ON CONFLICT DO NOTHING;
INSERT INTO cloudiff_v2.observed_state(resource_type,resource_id,revision,state,observed_at,node_id) VALUES ('node','00000000-0000-4000-8000-000000000098',2,'{"v":2}','2026-08-20T12:00:02Z','00000000-0000-4000-8000-000000000098');
INSERT INTO cloudiff_v2.observed_state(resource_type,resource_id,revision,state,observed_at,node_id) VALUES ('node','00000000-0000-4000-8000-000000000098',1,'{"v":1}','2026-08-20T12:00:01Z','00000000-0000-4000-8000-000000000098')
ON CONFLICT(resource_type,resource_id) DO UPDATE SET revision=EXCLUDED.revision,state=EXCLUDED.state,observed_at=EXCLUDED.observed_at WHERE EXCLUDED.observed_at>=cloudiff_v2.observed_state.observed_at;
DO $$ BEGIN IF (SELECT revision FROM cloudiff_v2.observed_state WHERE resource_id='00000000-0000-4000-8000-000000000098') <> 2 THEN RAISE EXCEPTION 'older observation overwrote newer'; END IF; END $$;
ROLLBACK;
