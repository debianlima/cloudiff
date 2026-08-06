from pathlib import Path
import ast
import re
import unittest

SOURCE = Path('components/control-plane/current-apps/supabase-mcp-broker-current/cloudif-supabase-mcp-broker.py').read_text()
TREE = ast.parse(SOURCE)
WANTED_ASSIGNMENTS = {'SENSITIVE_SCHEMA_RE', 'FORBIDDEN_SQL', 'UNSAFE_FUNCTION_LANGUAGE', 'RLS_ALLOWED', 'SCHEMA_ALLOWED'}
WANTED_FUNCTIONS = {'scan_sql', 'validate_sql'}
NODES = []
for node in TREE.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in WANTED_ASSIGNMENTS for t in node.targets):
        NODES.append(node)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in WANTED_FUNCTIONS:
        NODES.append(node)
MODULE = ast.Module(body=NODES, type_ignores=[])
ast.fix_missing_locations(MODULE)
NS = {'re': re, 'PermissionError': PermissionError, 'ValueError': ValueError}
exec(compile(MODULE, '<supabase-mcp-sql-policy>', 'exec'), NS)
scan_sql = NS['scan_sql']
validate_sql = NS['validate_sql']


class SupabaseMCPSQLPolicyTest(unittest.TestCase):
    def test_single_read_query_is_allowed(self):
        self.assertEqual(validate_sql('select id, nome from public.equipamentos limit 10', 'read'), ['select id, nome from public.equipamentos limit 10'])

    def test_read_mode_rejects_writes_and_multiple_statements(self):
        with self.assertRaisesRegex(PermissionError, 'read_only_sql_required'):
            validate_sql("update public.equipamentos set nome='x' where id=1", 'read')
        with self.assertRaisesRegex(ValueError, 'read_sql_single_statement_required'):
            validate_sql('select 1; select 2', 'read')

    def test_comments_literals_and_dollar_bodies_are_split_correctly(self):
        rows = scan_sql("select ';' as valor; -- ; oculto\nselect $$texto;interno$$")
        self.assertEqual(len(rows), 2)
        self.assertIn("select ';'", rows[0][0])
        self.assertIn('$$texto;interno$$', rows[1][0])

    def test_sensitive_schemas_are_rejected_even_when_quoted(self):
        for statement in ('select * from vault.decrypted_secrets', 'select * from "auth"."users"', 'select * from storage.objects'):
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(PermissionError, 'sensitive_schema_access_denied'):
                    validate_sql(statement, 'read')

    def test_server_file_role_and_copy_capabilities_are_rejected(self):
        statements = (
            "select pg_read_file('/etc/passwd')",
            "select \"pg_read_binary_file\"('/etc/passwd')",
            "copy public.t to '/tmp/data'",
            "create role invasor login",
            "alter system set shared_preload_libraries='x'",
            "select pg_terminate_backend(1)",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                with self.assertRaisesRegex(PermissionError, 'forbidden_sql_capability'):
                    validate_sql(statement, 'change')

    def test_function_languages_and_hidden_dangerous_bodies_are_rejected(self):
        unsafe = (
            "create function public.x() returns int language c as '/tmp/x.so','x'",
            "create function public.x() returns text language plpgsql as $$ begin return pg_read_file('/etc/passwd'); end $$",
            "create function public.x() returns void language plpgsql as $$ begin execute 'drop table public.t'; end $$",
            "create function public.x() returns int security definer language sql as $$ select 1 $$",
        )
        for statement in unsafe:
            with self.subTest(statement=statement):
                with self.assertRaises(PermissionError):
                    validate_sql(statement, 'schema')

    def test_safe_sql_and_plpgsql_functions_remain_possible(self):
        safe_sql = "create function public.soma(a int,b int) returns int language sql immutable as $$ select a+b $$"
        safe_trigger = "create function public.atualiza_data() returns trigger language plpgsql as $$ begin new.updated_at=now(); return new; end $$"
        self.assertEqual(validate_sql(safe_sql, 'schema'), [safe_sql])
        self.assertEqual(validate_sql(safe_trigger, 'schema'), [safe_trigger])

    def test_rls_and_schema_modes_are_narrow(self):
        self.assertEqual(validate_sql('create policy leitura on public.itens for select using (true)', 'rls')[0].split()[0].lower(), 'create')
        self.assertEqual(validate_sql('alter table public.itens enable row level security', 'rls')[0].split()[0].lower(), 'alter')
        with self.assertRaisesRegex(PermissionError, 'rls_statement_required'):
            validate_sql('drop table public.itens', 'rls')
        self.assertEqual(validate_sql('create table public.itens(id bigint primary key)', 'schema')[0].split()[0].lower(), 'create')
        with self.assertRaisesRegex(PermissionError, 'schema_statement_required'):
            validate_sql('truncate table public.itens', 'schema')

    def test_literals_do_not_trigger_keyword_false_positive(self):
        statement = "insert into public.auditoria(mensagem) values ('grant acesso ao usuário')"
        self.assertEqual(validate_sql(statement, 'change'), [statement])


if __name__ == '__main__':
    unittest.main()
