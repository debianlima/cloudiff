BEGIN;
CREATE OR REPLACE FUNCTION cloudiff_v2.claim_jobs_for_kinds(
    p_worker text,
    p_limit integer,
    p_lease_seconds integer,
    p_kinds text[]
)
RETURNS SETOF cloudiff_v2.jobs
LANGUAGE sql
AS $$
 WITH pool AS (
  SELECT DISTINCT ON (j.partition_key) j.job_id,j.partition_key,j.created_at
  FROM cloudiff_v2.jobs j
  WHERE j.kind = ANY(COALESCE(p_kinds,ARRAY[]::text[]))
    AND (
      (j.status='ready' AND j.ready_at<=now())
      OR (j.status='waiting_retry' AND j.retry_at IS NOT NULL AND j.retry_at<=now())
      OR (j.status='leased' AND j.lease_expires_at IS NOT NULL AND j.lease_expires_at<=now())
    )
    AND NOT EXISTS (
      SELECT 1 FROM cloudiff_v2.job_partition_leases pl
      WHERE pl.partition_key=j.partition_key AND pl.lease_expires_at>now()
    )
  ORDER BY j.partition_key,j.created_at,j.job_id
 ), locked AS (
  SELECT j.job_id,j.partition_key
  FROM cloudiff_v2.jobs j JOIN pool p ON p.job_id=j.job_id
  ORDER BY j.created_at,j.job_id
  FOR UPDATE OF j SKIP LOCKED
  LIMIT GREATEST(p_limit,0)
 ), acquired AS (
  INSERT INTO cloudiff_v2.job_partition_leases(partition_key,job_id,worker_id,lease_expires_at)
  SELECT l.partition_key,l.job_id,p_worker,now()+make_interval(secs=>GREATEST(p_lease_seconds,1))
  FROM locked l
  ON CONFLICT(partition_key) DO UPDATE
    SET job_id=EXCLUDED.job_id,worker_id=EXCLUDED.worker_id,
        lease_expires_at=EXCLUDED.lease_expires_at,acquired_at=now()
    WHERE cloudiff_v2.job_partition_leases.lease_expires_at<=now()
  RETURNING job_id
 ), claimed AS (
  UPDATE cloudiff_v2.jobs j
  SET status='leased',lease_owner=p_worker,
      lease_expires_at=now()+make_interval(secs=>GREATEST(p_lease_seconds,1)),
      retry_at=NULL,attempt=j.attempt+1,updated_at=now()
  FROM acquired a WHERE j.job_id=a.job_id
  RETURNING j.*
 ), attempts AS (
  INSERT INTO cloudiff_v2.job_attempts(job_id,attempt,worker_id,started_at,finished_at,outcome,error)
  SELECT c.job_id,c.attempt,p_worker,now(),NULL,NULL,NULL FROM claimed c
  ON CONFLICT(job_id,attempt) DO UPDATE
    SET worker_id=EXCLUDED.worker_id,started_at=EXCLUDED.started_at,
        finished_at=NULL,outcome=NULL,error=NULL
  RETURNING job_id
 ) SELECT c.* FROM claimed c JOIN attempts a USING(job_id);
$$;
COMMIT;
