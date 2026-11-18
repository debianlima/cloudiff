#!/usr/bin/env python3
"""Offline prototype of canonical Portal ACL revisions via SQLite triggers.

Only use against disposable SQLite fixtures. No production migration performed.
"""
import sqlite3

SCHEMA = '''
CREATE TABLE IF NOT EXISTS project_acl_revisions (
 slug TEXT PRIMARY KEY, revision INTEGER NOT NULL CHECK(revision >= 1)
);
CREATE TRIGGER IF NOT EXISTS cloudif_acl_project_insert_v1
AFTER INSERT ON projects BEGIN
 INSERT INTO project_acl_revisions(slug,revision) VALUES(NEW.slug,1)
 ON CONFLICT(slug) DO UPDATE SET revision=revision+1;
END;
CREATE TRIGGER IF NOT EXISTS cloudif_acl_owner_change_v1
AFTER UPDATE OF owner ON projects
WHEN COALESCE(OLD.owner,'') != COALESCE(NEW.owner,'') BEGIN
 INSERT INTO project_acl_revisions(slug,revision) VALUES(NEW.slug,1)
 ON CONFLICT(slug) DO UPDATE SET revision=revision+1;
END;
CREATE TRIGGER IF NOT EXISTS cloudif_acl_member_insert_v1
AFTER INSERT ON project_acl BEGIN
 INSERT INTO project_acl_revisions(slug,revision) VALUES(NEW.slug,1)
 ON CONFLICT(slug) DO UPDATE SET revision=revision+1;
END;
CREATE TRIGGER IF NOT EXISTS cloudif_acl_member_delete_v1
AFTER DELETE ON project_acl BEGIN
 INSERT INTO project_acl_revisions(slug,revision) VALUES(OLD.slug,1)
 ON CONFLICT(slug) DO UPDATE SET revision=revision+1;
END;
CREATE TRIGGER IF NOT EXISTS cloudif_acl_member_update_old_v1
AFTER UPDATE ON project_acl BEGIN
 INSERT INTO project_acl_revisions(slug,revision) VALUES(OLD.slug,1)
 ON CONFLICT(slug) DO UPDATE SET revision=revision+1;
END;
CREATE TRIGGER IF NOT EXISTS cloudif_acl_member_update_new_v1
AFTER UPDATE OF slug ON project_acl
WHEN OLD.slug!=NEW.slug BEGIN
 INSERT INTO project_acl_revisions(slug,revision) VALUES(NEW.slug,1)
 ON CONFLICT(slug) DO UPDATE SET revision=revision+1;
END;
-- Existing rows migrated with synthetic baseline revision 1; old backups still need reconciliation.
INSERT OR IGNORE INTO project_acl_revisions(slug,revision) SELECT slug,1 FROM projects;
'''


def install_disposable_schema(connection:sqlite3.Connection):
    """DDL proof only; not authorized for live Portal database."""
    connection.executescript(SCHEMA)


def read_canonical_snapshot(dbpath:str,project:str) -> dict:
    """Single SQLite read transaction ensures owner, ACL and revision are coherent."""
    con=sqlite3.connect('file:'+dbpath+'?mode=ro',uri=True,timeout=5)
    con.row_factory=sqlite3.Row
    try:
        con.execute('PRAGMA query_only=ON')
        con.execute('BEGIN')
        row=con.execute('''SELECT p.owner,r.revision FROM projects p
                          JOIN project_acl_revisions r ON r.slug=p.slug
                          WHERE p.slug=?''',(project,)).fetchone()
        if row is None:raise ValueError('revision_or_project_missing')
        owner=row['owner']
        if not isinstance(owner,str) or not owner.strip():raise ValueError('verified_owner_missing')
        members=con.execute('''SELECT subject_type,subject FROM project_acl
                               WHERE slug=? ORDER BY subject_type,subject''',(project,)).fetchall()
        acl=[{'type':r['subject_type'],'subject':r['subject']} for r in members]
        out={'project':project,'owner':owner.strip().lower(),'acl':acl,'acl_revision':row['revision']}
        con.commit()
        return out
    finally:con.close()
