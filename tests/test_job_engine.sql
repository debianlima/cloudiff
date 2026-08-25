\set ON_ERROR_STOP on
BEGIN;
INSERT INTO cloudiff_v2.jobs(job_id,kind,status,partition_key,idempotency_key,payload,max_attempts,created_at) VALUES
('00000000-0000-4000-8000-000000000301','test','ready','sql:A','itest-v5:sql-a1','{}',3,'2026-08-20T12:00:00Z'),
('00000000-0000-4000-8000-000000000302','test','ready','sql:A','itest-v5:sql-a2','{}',3,'2026-08-20T12:00:01Z'),
('00000000-0000-4000-8000-000000000303','test','ready','sql:B','itest-v5:sql-b1','{}',3,'2026-08-20T12:00:02Z');
DO $$ DECLARE c integer; BEGIN SELECT count(*) INTO c FROM cloudiff_v2.claim_jobs('sql-worker-1',10,30);IF c<>2 THEN RAISE EXCEPTION 'expected 2 partitions, got %',c;END IF;IF (SELECT count(*) FROM cloudiff_v2.jobs WHERE status='leased' AND partition_key='sql:A')<>1 THEN RAISE EXCEPTION 'partition A concurrent';END IF;END $$;
DO $$ DECLARE c integer; BEGIN SELECT count(*) INTO c FROM cloudiff_v2.claim_jobs('sql-worker-2',10,30);IF c<>0 THEN RAISE EXCEPTION 'second worker bypassed lease';END IF;END $$;
UPDATE cloudiff_v2.job_partition_leases SET lease_expires_at=now()-interval '1 second';
UPDATE cloudiff_v2.jobs SET lease_expires_at=now()-interval '1 second' WHERE status='leased';
DO $$ DECLARE c integer; BEGIN SELECT count(*) INTO c FROM cloudiff_v2.claim_jobs('sql-recovery',10,30);IF c<>2 THEN RAISE EXCEPTION 'expired leases not recovered, got %',c;END IF;END $$;
ROLLBACK;
