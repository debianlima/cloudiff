\set ON_ERROR_STOP on
BEGIN;
DO $$ BEGIN
  IF (SELECT count(*) FROM cloudiff_v2.projects) <> 0 THEN RAISE EXCEPTION 'projects must start empty'; END IF;
END $$;
INSERT INTO cloudiff_v2.jobs(job_id,kind,status,partition_key,idempotency_key,payload)
VALUES ('00000000-0000-4000-8000-000000000001','test','ready','test:1','idem:test:1','{}');
DO $$ BEGIN
  BEGIN
    INSERT INTO cloudiff_v2.jobs(job_id,kind,status,partition_key,idempotency_key,payload)
    VALUES ('00000000-0000-4000-8000-000000000002','test','ready','test:2','idem:test:1','{}');
    RAISE EXCEPTION 'expected unique violation';
  EXCEPTION WHEN unique_violation THEN NULL;
  END;
END $$;
DO $$ DECLARE c integer; BEGIN
  SELECT count(*) INTO c FROM cloudiff_v2.claim_jobs('test-worker',1,30);
  IF c <> 1 THEN RAISE EXCEPTION 'expected one claimed job, got %', c; END IF;
  IF NOT EXISTS (SELECT 1 FROM cloudiff_v2.jobs WHERE idempotency_key='idem:test:1' AND status='leased' AND lease_owner='test-worker') THEN
    RAISE EXCEPTION 'lease not applied';
  END IF;
END $$;
ROLLBACK;
